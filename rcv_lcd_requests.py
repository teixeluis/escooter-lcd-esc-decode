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

FLAG_PAS = 1
FLAG_CRUISE_CTL = 2
FLAG_SOFT_START = 3

parser = argparse.ArgumentParser(description='Listens to the requests sent by the e-Scooter JP LCD display via UART.')

parser.add_argument('serial_port', type=str,
                    help='the serial device for the communication')

args = parser.parse_args()

# Payload encryption key:

enc_key = bytes([0x7b,0x00,0x01,0x26,0x2f,0x24,0x25,0x2a,0x23,0x28,0x29,0x4e,0x77,0x4c,
                0x4d,0x52,0x4b,0x50,0x51,0x76,0x7f,0x74,0x75,0x7a,0x73,0x78,0x79,0x5e,
                0x07,0x5c,0x5d,0x62,0x5b,0x60,0x61,0x06,0x0f,0x04,0x05,0x0a,0x03,0x08,
                0x09,0x2e,0x57,0x2c,0x2d,0x32,0x2b,0x30,0x31,0x56,0x5f,0x54,0x55,0x5a,
                0x53,0x58,0x59,0x3e,0x67,0x3c,0x3d,0x42,0x3b,0x40,0x41,0x66,0x6f,0x64,
                0x65,0x6a,0x63,0x68,0x69,0x0e,0x37,0x0c,0x0d,0x12,0x0b,0x10,0x11,0x36,
                0x3f,0x34,0x35,0x3a,0x33,0x38,0x39,0x1e,0x47,0x1c,0x1d,0x22,0x1b,0x20,
                0x21,0x46,0x4f,0x44,0x45,0x4a,0x43,0x48,0x49,0x6e,0x17,0x6c,0x6d,0x72,
                0x6b,0x70,0x71,0x16,0x1f,0x14,0x15,0x1a,0x13,0x18,0x19,0x7e,0x27,0x7c,
                0x7d,0x02])

# Frame fields:

raw_frame = bytearray(FRAME_SIZE)
frame_seq = 0
entropy_key = 0
power_setting = 0
config_flags = 0
eabs = 0
checksum = 0
checksum_calc = 0

# state variables:

frame_byte = 0
payload_byte = 0
is_beginning = True
valid_frame = True
last_frame = datetime.datetime.now()

def decode_short(short_bytes):
    return int.from_bytes(short_bytes, byteorder='big')

def decode_flag(byte_val, position):
    return byte_val >> position & b'\x01'[0]

def decrypt_value(frame, orig_value):
    key_index = frame if frame < 128 else frame - 128

    if orig_value >= enc_key[key_index]:
        return  orig_value - enc_key[key_index]

    return 255 + orig_value - enc_key[key_index]


with serial.Serial(args.serial_port, BAUD_RATE, timeout=READ_TIMEOUT) as ser:
    while (byte := ser.read(1)):
        raw_frame[frame_byte] = byte[0]

        # 0x01 0x03 should be the beginning of a regular frame:

        if frame_byte == 0:
            if byte != b'\x01':
                print(f'Unexpected first byte: {byte}')
                valid_frame = False
        elif frame_byte == 1:
            if byte != b'\x03':
                print(f'Unexpected 2nd byte: {byte}')
                valid_frame = False                
        elif frame_byte == 2:
            # this is the frame sequence field
            frame_seq = byte[0]
            print(f'Got frame nr: {frame_seq}')
            if is_beginning and frame_seq != 2:
                print(f'Got unexpected sequence in first frame: {frame_seq}')
                valid_frame = False
            else:
                is_beginning = False
        #elif frame_byte == 3 or frame_byte == 4:
        #   print(f'Got the padding byte nr {frame_byte}.')
        elif frame_byte == 5:
            # Encrypted speed limiter field:
            enc_speed_limiter = byte[0]
        #elif frame_byte == 6:
        #    print(f'Got the padding byte nr {frame_byte}.')
        elif frame_byte == 7:
            power_setting = byte[0]
        #elif frame_byte == 8:
        #    print(f'Got the padding byte nr {frame_byte}.')
        elif frame_byte == 9:
            config_flags = byte[0]
        elif frame_byte == 10:
            eabs = byte[0]
        #elif frame_byte >= 11 or frame_byte <  14:
        #    print(f'Got the padding byte nr {frame_byte}.')            
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
                speed_limiter = decrypt_value(frame_seq, enc_speed_limiter)
                pas = decode_flag(raw_frame[6], FLAG_PAS)
                cruise_ctl = decode_flag(raw_frame[6], FLAG_CRUISE_CTL)
                soft_start = decode_flag(raw_frame[6], FLAG_SOFT_START)
                print(f'Time lapse: {delta_time}; Speed limiter: {speed_limiter}; PAS: {pas}; Cruise Ctl: {cruise_ctl}; Soft start: {soft_start}; Power limit: {raw_frame[7]}; EABS: {raw_frame[10]}')
            frame_byte = 0
            checksum_calc = 0
            valid_frame = True
