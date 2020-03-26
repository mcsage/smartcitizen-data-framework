from os import makedirs, walk
from os.path import join, exists
from shutil import copyfile
from src.saf import paths, configuration
from src.saf import std_out, read_csv_file, export_csv_file, get_localised_date
from src.data.device import device_wrapper
from traceback import print_exc
from datetime import timedelta
import yaml
import json

class test_wrapper:
	
	def __init__(self, test_name = ''):

		self.name = test_name
		self.path = join(paths['dataDirectory'], 'processed', self.name[:4], self.name[5:7], self.name)
		self.details = dict()
		self.devices = dict()
		self.descriptor = dict()
		self.descriptor['id'] = self.name
		self.cached_info = dict()
		self.ready_to_model = False
		self.options = configuration['test']

	def make(self):
		# Create folder structure under data subdir
		if not exists(self.path): makedirs(self.path)
		else: raise SystemError('Test already exists with this name. Since you want to create a new test, I will stop here so that I avoid to overwrite')
		
		std_out('Creating new test')
		self.update_descriptor()
		self.process_files()

		std_out ('Test creation finished', 'SUCCESS')

	def update_descriptor(self):
		if self.descriptor == {}: self.std_out('No descriptor file to update')

		# Add details to descriptor, or update them if there is anything in details
		for detail in self.details.keys(): self.descriptor[detail] = self.details[detail]

		# Add devices to descriptor
		for device_name in self.devices.keys(): self.process_device(device_name)

		# Create yaml with test description
		with open(join(self.path, 'test_description.yaml'), 'w') as yaml_file: yaml.dump(self.descriptor, yaml_file)
			
		std_out ('Test update Finished', 'SUCCESS')

	def add_details(self, details):
		'''
			details: a dict containing the information about the test. Minimum of:
				- project
				- commit
				- author
				- test_type
				- report
				- comment
		'''
		try:
			for detail in details.keys(): self.details[detail] = details[detail]
		except:
			std_out ('Error adding details', 'ERROR')
			print_exc()
			return
		else:
			std_out ('Added details', 'SUCCESS')

	def add_device(self, device):
		'''
			Adds a device to the test. The device has to be an instance of 'src.data.device'
		'''
		try:
			if device.id not in self.devices.keys(): self.devices[device.id] = device
		except:
			std_out (f'Add device {device.id} NOK', 'ERROR')
			print_exc()
			return
		else:
			std_out (f'Add device {device.id} OK', 'SUCCESS')

	def process_device(self, device_name):

		if 'devices' not in self.descriptor.keys(): self.descriptor['devices'] = dict()
		
		device = self.devices[device_name]
		device.processed_data_file = self.name + '_' + str(device.id) + '.csv'

		dvars = vars(device).copy()
		for discvar in ['readings', 'api_device', 'options', 'loaded']: 
			if discvar in dvars: dvars.pop(discvar)

		self.descriptor['devices'][device.id] = dvars
	
	def process_files(self):
		'''
			Processes the files for one test, given that the devices and details have been added
		'''

		std_out('Processing files')
		
		def get_raw_files():
				list_raw_files = []
				for device in self.devices.keys():
					if self.devices[device].source == 'csv':
						list_raw_files.append(self.devices[device].raw_data_file)
				
				return list_raw_files    
		
		def copy_raw_files(_raw_src_path, _raw_dst_path, _list_raw_files):

				try: 

					for item in _list_raw_files:
						s = join(_raw_src_path, item)
						d = join(_raw_dst_path, item)
						copyfile(s, d)

					std_out('Copy raw files: OK', 'SUCCESS')
					
					return True
				
				except:
					std_out('Problem copying raw files', 'ERROR')
					print_exc()
					return False
				
		def date_parser(s, a):
			return parser.parse(s).replace(microsecond=int(a[-3:])*1000)

		# Define Paths
		raw_src_path = join(paths['dataDirectory'], 'raw')
		raw_dst_path = join(self.path, 'raw')

		# Create Paths
		if not exists(raw_dst_path): makedirs(raw_dst_path)
		
		# Get raw files
		list_raw_files = get_raw_files()

		# Copy raw files and process data
		if len(list_raw_files):
			if copy_raw_files(raw_src_path, raw_dst_path, list_raw_files):	
			
				# Process devices
				for device_name in self.devices.keys():

					device = self.devices[device_name]

					if device.source == 'csv':

						std_out ('Processing csv from device {}'.format(device.id))
						src_path = join(raw_src_path, device.raw_data_file)
						dst_path = join(self.path, device.processed_data_file)

						# Load csv file, only localising and removing 
						df = read_csv_file(src_path, device.location, device.frequency, clean_na = None, index_name = device.sources[device.source]['index'], skiprows = device.sources[device.source]['header_skip'])
						df.to_csv(dst_path, sep=",")
					
			std_out('Processing files OK', 'SUCCESS')
		std_out(f'Test {self.name} path: {self.path}')

	def set_options(self, options):
		if 'load_cached_API' in options.keys(): self.options['load_cached_API'] = options['load_cached_API']
		if 'store_cached_API' in options.keys(): self.options['store_cached_API'] = options['store_cached_API']
		if 'clean_na' in options.keys(): self.options['clean_na'] = options['clean_na']
		if 'clean_na_method' in options.keys(): self.options['clean_na_method'] = options['clean_na_method']
		if 'frequency' in options.keys(): self.options['frequency'] = options['frequency']
	
	def load (self, options):
		
		# Load descriptor
		std_out(f'Loading test {self.name}', force = True)
		with open(join(self.path, 'test_description.yaml'), 'r') as descriptor_file:
			self.descriptor = yaml.load(descriptor_file, Loader = yaml.FullLoader)

		# Add devices
		for key in self.descriptor['devices'].keys():
			self.devices[key] = device_wrapper(self.descriptor['devices'][key]['blueprint'], self.descriptor['devices'][key])

		# Set options
		self.ready_to_model = False
		self.set_options(options)

		std_out(f'Using options: {options}')

		for key in self.devices.keys():
			
			device = self.devices[key]
			std_out(f'Loading device {device.id}')

			min_date_device = get_localised_date(device.min_date, device.location)
			max_date_device = get_localised_date(device.max_date, device.location)

			# TODO - Rename
			# # Name convertion
			# target_names = list()
			# test_names = list()

			# if device.metadata is not None:
			# 	std_out('Found metadata', 'SUCCESS')
				
			# 	# Use metadata to convert names
			# 	for item_test in device.metadata:
			# 		if device.metadata[item_test]['id'] == '0': continue

			# 		for item_target in self.data.current_names:
			# 			if self.data.current_names[item_target]['id'] == device.metadata[item_test]['id'] and item_test not in test_names:
			# 				target_names.append(self.data.current_names[item_target]['shortTitle'])
			# 				test_names.append(item_test)  
			# else:
			# 	std_out('No metadata found - skipping', 'WARNING')

			# If device comes from API, pre-check dates
			if device.source == 'api':

				if device.location is None: device.location = device.api_device.get_device_location()

				# Get last reading from API
				if 'get_date_last_reading' in dir(device.api_device): 
					last_reading_api = get_localised_date(device.api_device.get_date_last_reading(), device.location)

					if self.options['load_cached_API']:

						if not device.load(options = self.options, path = join(self.path, 'cached')):

							std_out(f'No valid cached data. Requesting device {device.id} to API', 'WARNING')
							min_date_to_load = min_date_device
							max_date_to_load = max_date_device
							load_API = True

						else:
							
							std_out(f'Loaded cached files from', 'SUCCESS')
							std_out(f'Checking if new data is to be loaded')

							# Get last reading from cached
							last_reading_cached = get_localised_date(device.readings.index[-1], device.location)

							# Check which dates to load
							if max_date_device is not None:
								std_out(f'Max date in test {max_date_device}')
								# Check what where we need to load data from, if any
								if last_reading_cached < max_date_device and last_reading_api > last_reading_cached + timedelta(hours=1):
									load_API = True
									combine_cache_API = True
									min_date_to_load = last_reading_cached
									max_date_to_load = min(max_date_device, last_reading_api)
									std_out('Loading new data from API')
								else:
									load_API = False
									std_out('No need to load new data from API', 'SUCCESS')
							else:
								# If no test data specified, check the last reading in the API
								if last_reading_api > last_reading_cached + timedelta(hours=self.options['cached_data_margin']):
									load_API = True
									combine_cache_API = True
									min_date_to_load = last_reading_cached
									max_date_to_load = last_reading_api
									std_out('Loading new data from API', 'WARNING')
								else:
									load_API = False
									std_out('No need to load new data from API', 'SUCCESS')
					else:
						min_date_to_load = min_date_device
						max_date_to_load = max_date_device
				else:
					if self.options['load_cached_API']: std_out('Cannot load cached data with an API that does not allow checking when was the last reading available', 'WARNING')

				# Load data from API if necessary
				if load_API:
					std_out('Downloading device from API')
					
					if last_reading_api is not None:
						# Check which max date to load
						if max_date_to_load is not None:
							if max_date_to_load > last_reading_api:
								# Not possible to load what has not been stored
								max_date_to_load = last_reading_api
							else:
								# Only request what we asked for
								max_date_to_load = max_date_to_load
						else:
							# Just put None and we will handle it later
							max_date_to_load = last_reading_api

						# Check which min date to load
						if min_date_to_load is not None:
							std_out('First reading requested: {}'.format(min_date_to_load))
							if min_date_to_load < last_reading_api:
								std_out('Requesting up to max available date in the API {}'.format(last_reading_api))
								min_date_to_load = min_date_to_load
							else:
								std_out('Discarding device. Min date requested is after last reading', 'WARNING')
								continue
						else:
							std_out('Requesting all available data', 'WARNING')
							# Just put None and we will handle it later
							min_date_to_load = None

					else:
						std_out('Discarding device. No max date available', 'WARNING')
						continue

					self.options['min_date'] = min_date_to_load
					self.options['max_date'] = max_date_to_load

					device.load(options = self.options)

			elif device.source == 'csv':
				device.load(options = self.options, path = self.path)
				
				# TODO rename columns
				# if len(target_names) == len(test_names) and len(target_names) > 0:
				# 	for i in range(len(target_names)):
				# 		if not (test_names[i] == '') and not (test_names[i] == target_names[i]) and test_names[i] in device.readings.columns:
				# 			device.readings.rename(columns={test_names[i]: target_names[i]}, inplace=True)
				# 			std_out('Renaming column {} to {}'.format(test_names[i], target_names[i]))

			if self.options['store_cached_API'] and device.loaded and device.source == 'api' and load_API:

				std_out(f'Caching files for {device.id}')

				cached_file_path = join(self.path, 'cached')
				if not exists(cached_file_path):
					std_out('Creating path for exporting cached data')
					makedirs(cached_file_path)
					
				if export_csv_file(cached_file_path, device.id, device.readings, forced_overwrite = True): std_out('Devices cached successfully', 'SUCCESS')

			if device.loaded: std_out(f'Device {device.id} has been loaded', 'SUCCESS')

		self.update_descriptor()