# -----------------------------------------------------------------------------
# Copyright (c) 2024, Lucid Vision Labs, Inc.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# -----------------------------------------------------------------------------

import ctypes
import sys
import time

from arena_api.__future__.save import Writer
from arena_api.buffer import BufferFactory
from arena_api.enums import PixelFormat
from arena_api.system import system

'''
Helios Heat Map: Introduction
    This example demonstrates the transformation of 3-dimensional data to produce
	2D and 3D heat maps. It uses a 3D-compatible camera. After verifying the camera,
    we snap an image, and generate a 2D heat map based on the z-coordinate data.
    It then saves the image as a JPEG file. It then also generates a 3D heat map
    based on the same data, and saves it as a PLY file.
'''

RGB_MIN = 0
RGB_MAX = 255
COLOR_BORDER_RED = 0
COLOR_BORDER_YELLOW = 375
COLOR_BORDER_GREEN = 750
COLOR_BORDER_CYAN = 1125
COLOR_BORDER_BLUE = 1500
TAB1 = "  "
TAB2 = "    "

# check if Helios2 camera used for the example
isHelios2 = False


def create_devices_with_tries():
	'''
	This function waits for the user to connect a device before raising
		an exception
	'''

	tries = 0
	tries_max = 1
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
			print(f'{TAB1}Created {len(devices)} device(s)')
			return devices
	else:
		raise Exception(f'{TAB1}No device found! Please connect a device and run '
						f'the example again.')


def validate_device(device):

	# validate if Scan3dCoordinateSelector node exists.
	# If not, it is (probably) not a Helios Camera running the example
	try:
		scan_3d_operating_mode_node = device. \
			nodemap['Scan3dOperatingMode'].value
	except KeyError:
		print(f'{TAB1}Scan3dCoordinateSelector node is not found. '
			  f'Please make sure that a Helios device is used for the example.\n')
		sys.exit()

	# validate if Scan3dCoordinateOffset node exists.
	# If not, it is (probably) that Helios Camera has an old firmware
	try:
		scan_3d_coordinate_offset_node = device. \
			nodemap['Scan3dCoordinateOffset'].value
	except KeyError:
		print(f'{TAB1}Scan3dCoordinateOffset node is not found. '
			  f'Please update Helios firmware.\n')
		sys.exit()

	# check if Helios2 camera used for the example
	device_model_name_node = device.nodemap['DeviceModelName'].value
	if 'HLT' or 'HTP' in device_model_name_node:
		global isHelios2
		isHelios2 = True


def get_rgb_colors_of_point_at_distance(z):

	# distance between red and yellow
	if COLOR_BORDER_RED <= z < COLOR_BORDER_YELLOW:
		yellow_percentage = z / COLOR_BORDER_YELLOW
		red = RGB_MAX
		green = RGB_MAX * yellow_percentage
		blue = RGB_MIN

	# distance between yellow and green
	elif COLOR_BORDER_YELLOW <= z < COLOR_BORDER_GREEN:
		green_percentage = (z - COLOR_BORDER_YELLOW) / COLOR_BORDER_YELLOW
		red = RGB_MAX - (RGB_MAX * green_percentage)
		green = RGB_MAX
		blue = RGB_MIN

	# distance between green and cyan
	elif COLOR_BORDER_GREEN <= z < COLOR_BORDER_CYAN:
		cyan_percentage = (z - COLOR_BORDER_GREEN) / COLOR_BORDER_YELLOW
		red = RGB_MIN
		green = RGB_MAX
		blue = RGB_MAX * cyan_percentage

	# distance between cyan and blue
	elif COLOR_BORDER_CYAN <= z <= COLOR_BORDER_BLUE:
		blue_percentage = (z - COLOR_BORDER_CYAN) / COLOR_BORDER_YELLOW
		red = RGB_MIN
		green = RGB_MAX - (RGB_MAX * blue_percentage)
		blue = RGB_MAX
	else:
		red = RGB_MIN
		green = RGB_MIN
		blue = RGB_MIN

	return int(red), int(green), int(blue)


def get_a_BGR8_distance_heatmap_ctype_array(buffer_3d, scale_z):

	# 3D buffer info -------------------------------------------------

	# "Coord3D_ABCY16s" and "Coord3D_ABCY16" pixelformats have 4
	# channels pre pixel. Each channel is 16 bits and they represent:
	#   - x position
	#   - y postion
	#   - z postion
	#   - intensity
	# the value can be dynamically calculated this way:
	#   int(buffer_3d.bits_per_pixel/16) # 16 is the size of each channel
	Coord3D_ABCY16_channels_per_pixel = buffer_3d_step_size = 4

	# Buffer.pdata is a (uint8, ctypes.c_ubyte) pointer. "Coord3D_ABCY16"
	# pixelformat has 4 channels, and each channel is 16 bits.
	# It is easier to deal with Buffer.pdata if it is cast to 16bits
	# so each channel value is read/accessed easily.
	# "Coord3D_ABCY16" might be suffixed with "s" to indicate that the data
	# should be interpereted as signed.
	pdata_16bit = ctypes.cast(buffer_3d.pdata, ctypes.POINTER(ctypes.c_int16))

	number_of_pixels = buffer_3d.width * buffer_3d.height

	# out array info -------------------------------------------------

	BGR8_channels_per_pixel = array_bgr8_step_size = 3  # Blue, Green, Red
	BGR8_channel_size_bits = 8
	BGR8_pixel_size_bytes = BGR8_channel_size_bits * BGR8_channels_per_pixel
	array_BGR8_size_in_bytes = BGR8_pixel_size_bytes * number_of_pixels

	# array to return
	# c_byte and not c_ubyte because it is signed data
	CustomArrayType = (ctypes.c_byte * array_BGR8_size_in_bytes)
	array_BGR8_for_jpg = CustomArrayType()

	# iterate --------------------------------------------------------

	# iterate over two arrays with different internals
	# buffer_3d  : [x][y][z][a] | [x][y][z][a] | ... (each [] is 16 bit)
	# buffer_rgp : [b][g][r]    | [b][g][r]    | ... (each [] is 8 bit)
	buffer_3d_pixel_index = 0
	array_bgr8_pixel_index = 0
	for _ in range(number_of_pixels):

		# Isolate the z channel.
		# In one pixel:
		#   The first channel is the x coordinate,
		#   the second channel is the y coordinate,
		#   the third channel is the z coordinate, and
		#   the fourth channel is intensity.
		# The z coordinate is what used to determine the coloring
		z = pdata_16bit[buffer_3d_pixel_index + 2]

		# Convert z to millimeters
		#   The z data converts at a specified ratio to mm, so by
		#   multiplying it by the Scan3dCoordinateScale for CoordinateC, we
		#   can convert it to millimeters and can then compare it to the
		#   maximum distance of 1500mm.
		z = int(z * scale_z)

		# color respons to the z distance
		red, green, blue = get_rgb_colors_of_point_at_distance(z)

		# fill into the current pixel in BGR order not RGB
		array_BGR8_for_jpg[array_bgr8_pixel_index] = blue
		array_BGR8_for_jpg[array_bgr8_pixel_index + 1] = green
		array_BGR8_for_jpg[array_bgr8_pixel_index + 2] = red

		# next pixel index corresping index
		buffer_3d_pixel_index += buffer_3d_step_size
		array_bgr8_pixel_index += array_bgr8_step_size

	return array_BGR8_for_jpg


def get_a_RGB_colring_ctype_array(buffer_3d, scale_z):

	# 3D buffer info -------------------------------------------------

	# "Coord3D_ABCY16s" and "Coord3D_ABCY16" pixelformats have 4
	# channels pre pixel. Each channel is 16 bits and they represent:
	#   - x position
	#   - y postion
	#   - z postion
	#   - intensity
	# the value can be dinamically calculated this way:
	#   int(buffer_3d.bits_per_pixel/16) # 16 is the size of each channel
	Coord3D_ABCY16_channels_per_pixel = buffer_3d_step_size = 4

	# Buffer.pdata is a (uint8, ctypes.c_ubyte) pointer. "Coord3D_ABCY16"
	# pixelformat has 4 channels, and each channel is 16 bits.
	# It is easier to deal with Buffer.pdata if it is cast to 16bits
	# so each channel value is read/accessed easily.
	# "Coord3D_ABCY16" might be suffixed with "s" to indicate that the data
	# should be interpereted as signed.
	pdata_16bit = ctypes.cast(buffer_3d.pdata, ctypes.POINTER(ctypes.c_int16))

	number_of_pixels = buffer_3d.width * buffer_3d.height

	# out array info -------------------------------------------------

	RGB8_channels_per_pixel = array_rgb8_step_size = 3  # RED, Green, Blue
	RGB8_channel_size_bits = 8
	RGB8_pixel_size_bytes = RGB8_channel_size_bits * RGB8_channels_per_pixel
	array_RGB8_size_in_bytes = RGB8_pixel_size_bytes * number_of_pixels

	# array to return
	# c_byte and not c_ubyte because it is signed data
	CustomArrayType = (ctypes.c_byte * array_RGB8_size_in_bytes)
	array_RGB8_for_ply_coloring = CustomArrayType()

	# iterate --------------------------------------------------------

	# iterate over two arrays with different internals
	# buffer_3d  : [x][y][z][a] | [x][y][z][a] | ... (each [] is 16 bit)
	# buffer_rgp : [r][g][b]    | [r][g][b]    | ... (each [] is 8 bit)
	buffer_3d_pixel_index = 0
	array_rgb8_pixel_index = 0
	for _ in range(number_of_pixels):

		# Isolate the z channel.
		# In one pixel:
		#   The first channel is the x coordinate,
		#   the second channel is the y coordinate,
		#   the third channel is the z coordinate, and
		#   the fourth channel is intensity.
		# The z coordinate is what used to determine the coloring
		z = pdata_16bit[buffer_3d_pixel_index + 2]

		# Convert z to millimeters
		#   The z data converts at a specified ratio to mm, so by
		#   multiplying it by the Scan3dCoordinateScale for CoordinateC,  we
		#   are able to convert it to millimeters and can then compare it to the
		#   maximum distance of 1500mm.
		z = int(z * scale_z)

		# color respons to the z distance
		red, green, blue = get_rgb_colors_of_point_at_distance(z)

		# fill into the current pixel in RGB order not BGR
		array_RGB8_for_ply_coloring[array_rgb8_pixel_index] = red
		array_RGB8_for_ply_coloring[array_rgb8_pixel_index + 1] = green
		array_RGB8_for_ply_coloring[array_rgb8_pixel_index + 2] = blue

		# next pixel index corresping index
		buffer_3d_pixel_index += buffer_3d_step_size
		array_rgb8_pixel_index += array_rgb8_step_size

	return array_RGB8_for_ply_coloring


def example_entry_point():
	#
	# This example demonstrates saving an RGB heatmap of a 3D image. It
	# captures a 3D image, interprets the ABCY data to retrieve the
	# distance value for each pixel and then converts this data into a BGR
	# and an RGB buffer. The BGR buffer is used to create a jpg heatmap
	# image and the RGB buffer is used to color the ply image.
	#

	# Create a device
	devices = create_devices_with_tries()
	device = system.select_device(devices)

	validate_device(device)

	# Get device stream nodemap
	tl_stream_nodemap = device.tl_stream_nodemap

	# Enable stream auto negotiate packet size
	tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True

	# Enable stream packet resend
	tl_stream_nodemap['StreamPacketResendEnable'].value = True

	# Store nodes' initial values ---------------------------------------------
	nodemap = device.nodemap

	# get node values that will be changed in order to return their values at
	# the end of the example
	pixelFormat_initial = nodemap['PixelFormat'].value
	operating_mode_initial = nodemap['Scan3dOperatingMode'].value

	# Set nodes --------------------------------------------------------------
	# - pixelformat to Coord3D_ABCY16
	# - 3D operating mode to Distance1500mm
	print(f'\n{TAB1}Settings nodes:')
	pixel_format = PixelFormat.Coord3D_ABCY16  # unsigned data
	print(f'{TAB1}Setting pixelformat to { pixel_format.name}')
	nodemap.get_node('PixelFormat').value = pixel_format

	print(f'{TAB1}Setting 3D operating mode')
	if isHelios2 is True:
		nodemap['Scan3dOperatingMode'].value = 'Distance3000mmSingleFreq'
	else:
		nodemap['Scan3dOperatingMode'].value = 'Distance1500mm'

	# Get node values ---------------------------------------------------------
	# get z coordinate scale in order to convert z values to mm
	print(f'{TAB1}Get z coordinate scale from nodemap')
	nodemap["Scan3dCoordinateSelector"].value = "CoordinateC"
	scale_z = nodemap["Scan3dCoordinateScale"].value

	# Grab buffers ------------------------------------------------------------

	# Starting the stream allocates buffers and begins filling them with data.
	with device.start_stream(1):

		print(f'\n{TAB1}Stream started with 1 buffer')
		print(f'{TAB1}Get a buffer')

		# get_buffer would timeout or return 1 buffers
		buffer_3d = device.get_buffer()
		print(f'{TAB1}buffer received')

		# JPG FILE (2D heat map) -------------------------------------

		print(f'{TAB2}Creating BGR8 array from buffer')
		array_BGR8_for_jpg = get_a_BGR8_distance_heatmap_ctype_array(buffer_3d,
																	scale_z)
		uint8_ptr = ctypes.POINTER(ctypes.c_ubyte)
		ptr_array_BGR8_for_jpg = uint8_ptr(array_BGR8_for_jpg)
		bits_per_pixel =  PixelFormat.get_bits_per_pixel(PixelFormat.BGR8)
		array_BGR8_for_jpg_size_in_bytes = int(buffer_3d.width * buffer_3d.height * bits_per_pixel / 8)

		heat_buffer = BufferFactory.create(ptr_array_BGR8_for_jpg,
										array_BGR8_for_jpg_size_in_bytes,
										buffer_3d.width,
										buffer_3d.height,
										PixelFormat.BGR8)

		# create an image writer
		# The writer, optionally, can take width, height, and bits per pixel
		# of the image(s) it would save. if these arguments are not passed
		# at run time, the first buffer passed to the Writer.save()
		# function will configure the writer to the arguments buffer's width,
		# height, and bits per pixel

		# takes the setting of writer from buffer
		writer_jpg = Writer.from_buffer(heat_buffer)
		# save function takes a buffer made with BufferFactory that's why
		# heat_buffer was created though BufferFactory in the previous
		# steps
		writer_jpg.save(heat_buffer, 'heatmap.jpg')

		# buffers created with BufferFactory must be destroyed
		BufferFactory.destroy(heat_buffer)

		# PLY FILE (3D heat map)--------------------------------------

		print(f'{TAB2}Creating RGB8 array from buffer')
		array_RGB_colors = get_a_RGB_colring_ctype_array(buffer_3d, scale_z)

		uint8_ptr = ctypes.POINTER(ctypes.c_ubyte)
		ptr_array_RGB_colors = uint8_ptr(array_RGB_colors)

		writer_ply = Writer()
		# save function
		# buffer :
		#   buffer to save.
		# pattern :
		#   default name for the image is 'image_<count>.jpg' where count
		#   is a pre-defined tag that gets updated every time a buffer image
		#   is saved. More custom tags can be added using
		#   Writer.register_tag() function
		# kwargs (optional args) ignored if not an .ply image:
		#   - 'filter_points' default is True.
		#       Filters NaN points (A = B = C = -32,678)
		#   - 'is_signed' default is False.
		#       If pixel format is signed for example PixelFormat.Coord3D_A16s
		#       then this arg must be passed to the save function else
		#       the results would not be correct
		#   - 'scale' default is 0.25.
		#   - 'offset_a', 'offset_b' and 'offset_c' default to 0.0
		writer_ply.save(buffer_3d, 'heatmap.ply',
						color=ptr_array_RGB_colors,
						filter_points=True)

		# Requeue the chunk data buffers
		device.requeue_buffer(buffer_3d)
		print(f'{TAB1}Image buffer requeued')

	# When the scope of the context manager ends, then 'Device.stop_stream()'
	# is called automatically
	print(f'{TAB1}Stream stopped')

	# Clean up ----------------------------------------------------------------

	# restores initial node values
	nodemap['PixelFormat'].value = pixelFormat_initial
	nodemap['Scan3dOperatingMode'].value = operating_mode_initial

	# Destroy all created devices. This call is optional and will
	# automatically be called for any remaining devices when the system module
	#  is unloading.
	system.destroy_device()
	print(f'{TAB1}Destroyed all created devices')


if __name__ == '__main__':
	print('\nWARNING:\nTHIS EXAMPLE MIGHT CHANGE THE DEVICE(S) SETTINGS!')
	print('THIS EXAMPLE IS DESIGNED FOR HELIOUS 3D CAMERAS WITH LATEST '
		'FIRMWARE ONLY!')
	print('\nExample started\n')
	example_entry_point()
	print('\nExample finished successfully')
