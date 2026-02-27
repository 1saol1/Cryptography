import ctypes

def zero_memory(data: bytearray):

    length = len(data)
    ptr = (ctypes.c_char * length).from_buffer(data)
    for i in range(length):
        ptr[i] = 0
