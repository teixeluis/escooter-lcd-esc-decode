import argparse
import sys
import binascii
import serial
import datetime

FRAME_SIZE = 15
PAYLOAD_SIZE = 9
BAUD_RATE = 1200
READ_TIMEOUT = 30
WHEEL_PERIMETER = 0.8777

FLAG_TURBO = 0
FLAG_REGEN = 3
FLAG_BRAKES = 5

parser = argparse.ArgumentParser(description='Listens to the responses sent from a e-Scooter JP ESC via UART.')

parser.add_argument('serial_port', type=str,
                    help='the serial device for the communication')

args = parser.parse_args()

# Frame fields:

raw_frame = bytearray(FRAME_SIZE)
frame_seq = 0
pad_byte_1 = 0
pad_byte_2 = 0
entropy_key = 0
data_payload = bytearray(PAYLOAD_SIZE)
checksum = 0
checksum_calc = 0

# state variables:

frame_byte = 0
payload_byte = 0
is_beginning = True
last_frame = datetime.datetime.now()

def decode_flag(byte_val, position):
    return byte_val >> position & b'\x01'[0]

def convert_payload(orig_payload, entropy_val):
    conv_payload = bytearray(PAYLOAD_SIZE)

    for i in range(PAYLOAD_SIZE):
        #conv_payload[i] = orig_payload[i] ^ entropy_val
        if orig_payload[i] >= entropy_val:
            conv_payload[i] =  orig_payload[i] - entropy_val
        else:
            conv_payload[i] = 255 + orig_payload[i] - entropy_val

    return conv_payload

def decode_speed(rpm_bytes):
    # Empirically determined that reported value is about 75% of wheel RPM.
    # LCD probably takes into account the number of magnetic pole pairs
    # (P02 setting) to obtain the correct coefficient:

    rpm = 1.33 * int.from_bytes(rpm_bytes, byteorder='big')

    speed = (rpm * WHEEL_PERIMETER * 60) / 1000

    return speed

def decode_short(short_bytes):
    return int.from_bytes(short_bytes, byteorder='big')

valid_frame = True

with serial.Serial(args.serial_port, BAUD_RATE, timeout=READ_TIMEOUT) as ser:
    while (byte := ser.read(1)):
        raw_frame[frame_byte] = byte[0]

        if frame_byte == 0:
            # let's assume this is the beginning of a regular frame:
            if byte != b'\x36':
                print(f'Unexpected first byte: {byte}')
                valid_frame = False
        elif frame_byte == 1:
            # this is the frame sequence field
            frame_seq = byte[0]
            print(f'Got frame nr: {int(frame_seq)}')
            if is_beginning and frame_seq != 2:
                print(f'Got unexpected sequence in first frame: {frame_seq}')
                valid_frame = False
            else:
                is_beginning = False
        elif frame_byte == 2:
            # 1st padding byte (apparently no data meaning):
            pad_byte_1 = byte[0]
        elif frame_byte == 3:
            # entropy byte (data bytes that follow are XOR'ed with this value)
            entropy_key = byte[0]
        elif frame_byte == 4 or frame_byte == 5:
            # data bytes (1st block)
            data_payload[frame_byte - 4] = byte[0]
        elif frame_byte == 6:
            # 2nd padding byte (apparently no data meaning):
            pad_byte_2 = byte[0]
        elif frame_byte >= 7 and frame_byte < 14:
            # date bytes (2nd block)
            data_payload[frame_byte - 5] = byte[0]
        elif frame_byte == 14:
            # checksum:
            checksum = byte[0]

        if frame_byte < 14 and valid_frame:
            checksum_calc = checksum_calc ^ byte[0]
            frame_byte += 1
        else:
            curr_frame = datetime.datetime.now()
            delta_time = curr_frame - last_frame
            last_frame = curr_frame

            # print the raw frame:
            print('Raw frame:  ' + binascii.hexlify(raw_frame, ' ').decode("utf-8"))

            # let's decode and print the data:
            if checksum_calc == 0 or checksum != checksum_calc:
                print("Checksums don't match:")
                print(f'Parsed checksum: {checksum}')
                print(f'Calculated checksum: {checksum_calc}')
            else:
                print(f'Padding bytes: {pad_byte_1} {pad_byte_2}')
                conv_payload = convert_payload(data_payload, entropy_key)
                print('Converted payload: ' + binascii.hexlify(conv_payload, ' ').decode("utf-8"))
                
                speed = decode_speed([conv_payload[2], conv_payload[3]])
                wheel_spin = decode_short([conv_payload[2], conv_payload[3]])
                power = decode_short([conv_payload[4], conv_payload[5]])
                unk_field = decode_short([conv_payload[6], conv_payload[7]])

                turbo = decode_flag(conv_payload[0], FLAG_TURBO)
                regen = decode_flag(conv_payload[0], FLAG_REGEN)
                brakes = decode_flag(conv_payload[0], FLAG_BRAKES)

                print(f'Time lapse: {delta_time}; Wheel spin: {wheel_spin:.0f}; Speed: {speed:.1f}; Power: {power:.0f}; Turbo: {turbo}; Regen: {regen}; Brakes: {brakes}; Unknown field: {unk_field:.1f}')
            frame_byte = 0
            checksum_calc = 0
            valid_frame = True
