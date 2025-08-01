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

import time

from arena_api.system import system

'''
Acquisition: Introduction
	This example introduces the basics of image acquisition. This includes
	setting image acquisition and buffer handling modes, setting the device to
	automatically negotiate packet size, and setting the stream packet resend
	node before starting the image stream. The example then starts acquiring
	images by grabbing and requeuing buffers, and retrieving data on images
	before finally stopping the image stream.
'''
TAB1 = "  "
TAB2 = "    "


def create_devices_with_tries():
	'''
	This function waits for the user to connect a device before raising
		an exception
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
			print(f'{TAB1}Created {len(devices)} device(s)')
			return devices
	else:
		raise Exception(f'{TAB1}No device found! Please connect a device and run '
						f'the example again.')


def configure_and_get_image_buffers(device):

	nodemap = device.nodemap
	tl_stream_nodemap = device.tl_stream_nodemap
	nodes = device.nodemap.get_node(['Width', 'Height'])

	# Store initial settings, to restore later
	width_initial = nodes['Width'].value
	height_initial = nodes['Height'].value

	# Set features before streaming.-------------------------------------------
	initial_acquisition_mode = nodemap.get_node("AcquisitionMode").value

	nodemap.get_node("AcquisitionMode").value = "Continuous"
	'''
	Set buffer handling mode.
		Set buffer handling mode before starting the stream. Starting the stream
		requires the buffer handling mode to be set beforehand. The buffer
		handling mode determines the order and behavior of buffers in the
		underlying stream engine. Setting the buffer handling mode to
		'NewestOnly' ensures the most recent image is delivered, even if it means
		skipping frames.
	'''
	tl_stream_nodemap["StreamBufferHandlingMode"].value = "NewestOnly"

	'''
	Enable stream auto negotiate packet size
		Setting the stream packet size is done before starting the stream.
		Setting the stream to automatically negotiate packet size instructs the
		camera to receive the largest packet size that the system will allow.
		This generally increases frame rate and results in fewer interrupts per
		image, thereby reducing CPU load on the host system. Ethernet settings
		may also be manually changed to allow for a larger packet size.
	'''
	tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True

	'''
	Enable stream packet resend
		Enable stream packet resend before starting the stream. Images are sent
		from the camera to the host in packets using UDP protocol, which includes
		a header image number, packet number, and timestamp information. If a
		packet is missed while receiving an image, a packet resend is requested
		and this information is used to retrieve and redeliver the missing packet
		in the correct order.
	'''
	tl_stream_nodemap['StreamPacketResendEnable'].value = True

	# Set width and height to their max values
	print(f'{TAB1}Setting \'Width\' and \'Height\' Nodes value to their '
		'max values')
	nodes['Width'].value = nodes['Width'].max
	nodes['Height'].value = nodes['Height'].max

	number_of_buffers = 20

	'''
	Starting the stream allocates buffers, which can be passed in as
		an argument (default: 10), and begins filling them with data. Buffers
		must later be requeued to avoid memory leaks.
	'''
	device.start_stream(number_of_buffers)
	print(f'{TAB1}Stream started with {number_of_buffers} buffers')

	'''
	Device.get_buffer() returns buffers:
		Device.get_buffer() with no arguments returns one buffer(NOT IN A LIST)
		Device.get_buffer(20) returns 20 buffers(IN A LIST)
	'''
	print(f'{TAB1}Get {number_of_buffers} buffers in a list')
	buffers = device.get_buffer(number_of_buffers)

	'''
	Print image buffer info
		Buffers contain image data. Image data can also be copied and converted
		using BufferFactory. That is necessary to retain image data, as we must
		also requeue the buffer.
	'''
	for count, buffer in enumerate(buffers):
		print(f'{TAB2}buffer{count:{2}} received | '
			f'Width = {buffer.width} pxl, '
			f'Height = {buffer.height} pxl, '
			f'Pixel Format = {buffer.pixel_format.name}')

	
	'''
	'Device.requeue_buffer()' takes a buffer or many buffers in a list or tuple.
	returns them to the queue. Failure to requeue can lead to memory leaks or
	running out of buffers.
	'''
	device.requeue_buffer(buffers)
	print(f'{TAB1}Requeued {number_of_buffers} buffers')

	'''
	Stop stream: must be done before closing device
	'''
	device.stop_stream()
	print(f'{TAB1}Stream stopped')

	# Restore initial values
	nodemap.get_node("AcquisitionMode").value = initial_acquisition_mode
	nodemap.get_node("Width").value = width_initial
	nodemap.get_node("Height").value = height_initial


def example_entry_point():

	# Get connected devices ---------------------------------------------------

	# Create a device
	devices = create_devices_with_tries()
	device = system.select_device(devices)

	# Configure device and grab images ----------------------------------------

	configure_and_get_image_buffers(device)

	# Clean up ----------------------------------------------------------------

	'''
	Destroy device. This call is optional and will automatically be
		called for any remaining devices when the system module is unloading.
	'''
	system.destroy_device()
	print(f'{TAB1}Destroyed all created devices')


if __name__ == '__main__':
	print('Example started\n')
	example_entry_point()
	print('\nExample finished successfully')
