import time
from arena_api.system import system
import numpy as np

TAB1 = "  "

def update_create_devices():
	'''
	Waits for the user to connect a device before raising an
		exception if it fails
	'''
	tries = 0
	tries_max = 6
	sleep_time_secs = 10
	while tries < tries_max:  # Wait for device for 60 seconds
		devices = system.create_device()
		if not devices:
			print(
				f'{TAB1}Try {tries+1} of {tries_max}: waiting for {sleep_time_secs} '
				f'secs for a device to be connected!')
			for sec_count in range(sleep_time_secs):
				time.sleep(1)
				print(f'{TAB1}{sec_count + 1 } seconds passed ',
					'.' * sec_count, end='\r')
			tries += 1
		else:
			return devices
	else:
		raise Exception(f'{TAB1}No device found! Please connect a device and run '
						f'the example again.')

devices = update_create_devices()
device = system.select_device(devices)

import numpy as np
import cv2

with device.start_stream():
    buffer = device.get_buffer()
    print(f"{TAB1}Acquire Image")

    data = buffer.data
    width = buffer.width
    height = buffer.height
    pixel_format = buffer.pixel_format

    # Convert list to bytes
    byte_data = bytes(data)

    # Convert to numpy array and reshape
    image = np.frombuffer(byte_data, dtype=np.uint8).reshape((height, width))

    cv2.imwrite("acquired_image.png", image)
    print(f"{TAB1}Image saved as acquired_image.png")

    # Requeue buffer
    device.requeue_buffer(buffer)