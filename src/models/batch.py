import itertools
from os.path import basename, normpath, join
import json
from src.data.recording import recording
from src.models.model_tools import model_wrapper
import numpy as np
import traceback

class batch_analysis:
    append_alphasense = 'PRE'

    def __init__(self, tasksFile, verbose = False):
        try:
            self.verbose = verbose
            self.records = recording(verbose = self.verbose)
            self.tasks = json.load(open(tasksFile, 'r'))
            self.available_tests = self.records.available_tests()
        
        except:
            raise SystemError('Could not initialise object')
        
        else:
            self.std_out('Object initialised successfully')

    def std_out(self, msg):
        if self.verbose: print(msg)

    def load_data(self, tests, options):

        try:
            for data in tests:
                # Load each of the tests
                self.records.load_recording_database(data, self.available_tests[data], 
                                                    target_raster = options['target_raster'],
                                                    clean_na = options['clean_na'],
                                                    clean_na_method = options['clean_na_method'],
                                                    load_cached_API = options['use_cache'], 
                                                    cache_API = options['use_cache'])
        except:
            self.std_out('Problem loading data')
            traceback.print_exc()
            return False
        else:
            self.std_out('Data load OK')
            return True

    def pre_process_data(self, task, tests):
        
            for data in tests:
                self.std_out('Pre-processing {}'.format(data))
                try:
                    # Alphasense pollutant calculation based on baseline method
                    if 'alphasense' in task['pre-processing']:
                        
                        # Assume we need to pre-processed:
                        pre_processing_needed = True
                        
                        # Find out if in the cached, we have something that matches our variables
                        if task['options']['use_cache']:
                            self.std_out('Checking if we can use cached data')
                            # Open cached info file
                            with open(join(self.available_tests[data], 'cached', 'cache_info.json')) as handle:
                                cached_info = json.loads(handle.read())
                            
                            # Check there is pre-processing done in cached info
                            if 'pre-processing' in cached_info.keys():
                                if 'alphasense' in cached_info['pre-processing'].keys():
                                    # Check if the pre-processed parameters are the right ones. Also, that there is no new data to process
                                    if cached_info['pre-processing']['alphasense'] == task['pre-processing']['alphasense'] and cached_info['new_data_wo_process'] == False:
                                        self.std_out('Using cached data, no need to preprocess')
                                        pre_processing_needed = False

                        if pre_processing_needed:
                            self.std_out('Pre processing cannot be loaded from cached, calculating')
                            
                            # Variables for the two methods (deltas or ALS)
                            variables = list()
                            
                            baseline_method = task['pre-processing']['alphasense']['baseline_method']
                            parameters = task['pre-processing']['alphasense']['parameters']
                            
                            if baseline_method == 'deltas':
                                variables.append(np.arange(parameters[0], parameters[1], parameters[2]))
                            elif baseline_method == 'als':
                                variables.append([parameters['lambda'], parameters['p']])
                            
                            variables.append(task['pre-processing']['alphasense']['methods'])
                            variables.append(task['pre-processing']['alphasense']['overlapHours'])
                            variables.append(baseline_method)

                            # Display options
                            options = dict()
                            options['checkBoxDecomp'] = False
                            options['checkBoxPlotsIn'] = False
                            options['checkBoxPlotsResult'] = False
                            options['checkBoxVerb'] = False
                            options['checkBoxStats'] = False
                            # Calculate Alphasense
                            self.records.calculateAlphaSense(data, self.append_alphasense, variables, options)
                            
                            # Store the data in the info file and export csvs for next time
                            if task['options']['use_cache']:
                                # Set the flag of pre-processed data to False
                                cached_info['new_data_wo_process'] = False
                                # Store what we used as parameters for the pre-processing
                                cached_info['pre-processing'] = dict()
                                cached_info['pre-processing']['alphasense'] = task['pre-processing']['alphasense']
                                self.std_out('Caching info')

                                # Dump it
                                with open(join(self.available_tests[data], 'cached', 'cache_info.json'), 'w') as file:
                                    json.dump(cached_info, file)

                                self.std_out('Caching files')
                                # Save the files in the corresponding folder
                                for device in self.records.readings[data]['devices'].keys():
                                    if 'alphasense' in self.records.readings[data]['devices'][device].keys():
                                        filePath = join(self.available_tests[data], 'cached')
                                        self.records.exportCSVFile(filePath, device, self.records.readings[data]['devices'][device]['data'], forced_overwrite = True)

                    # TO-DO put other pre-processing options here - filtering, smoothing?
                except:
                    self.std_out("Problem processing test {}".format(data))
                    traceback.print_exc()
                    return False
                else:
                    self.std_out("Pre-processing test {} OK ".format(data))
            
            return True

    def sanity_checks(self, task, tests, has_model):

        # Sanity check for test presence
        if not all([self.available_tests.__contains__(i) for i in tests]):
            self.std_out ('Not all tests are available, review data input')
            return False
        
        else:
            # Cosmetic output
            self.std_out('Test presence check passed')
            
            # Check here if all the tuple_features are in each of the tests (accounting for the pre_processing)
            if has_model:
                
                # Get features
                features = task['model']['data']['features']
                features_names = [features[key] for key in features.keys() if key != 'REF']
                reference_name = features['REF']

                datasets = ['train', 'test']

                pollutant_index = {'CO': 1, 'NO2': 2, 'O3': 3}

                # Do it for both, train and test, if they exist
                for dataset in datasets:
                    self.std_out('Checking validity of {} input'.format(dataset))
                    # Check for datasets that are not reference
                    if dataset in task['model']['data'].keys():
                        for test in task['model']['data'][dataset].keys():
                            for device in task['model']['data'][dataset][test]:
                                # Get columns of the test
                                all_columns = list(self.records.readings[test]['devices'][device]['data'].columns)

                                # Add the pre-processing ones and if we can pre-process
                                if 'pre-processing' in task.keys(): 
                                    if 'alphasense'in task['pre-processing'].keys():
                                        # Check for each pollutant
                                        for pollutant in task['pre-processing']['alphasense']['methods'].keys():
                                            self.std_out('Checking pre-processing for {}'.format(pollutant))
                                            # Define who should be the columns
                                            minimum_alpha_columns = ['GB_{}W'.format(pollutant_index[pollutant]), 'GB_{}A'.format(pollutant_index[pollutant])]
                                            # Check if we can pre-process alphasense data with working and auxiliary electrode
                                            if not all([all_columns.__contains__(i) for i in minimum_alpha_columns]): return False
                                            # We know we can pre-process, add the result of the pre-process to the columns
                                            
                                            all_columns.append(pollutant + '_' + self.append_alphasense)
                                        
                                        if not all([all_columns.__contains__(i) for i in features_names]): return False
                                        
                            # In case of training dataset, check that the reference exists
                            if dataset == 'train':
                                found_ref = False
                                for device in self.records.readings[test]['devices'].keys():
                                    if 'is_reference' in self.records.readings[test]['devices'][device].keys():
                                        reference_dataframe = device
                                        if not (reference_name in self.records.readings[test]['devices'][device]['data'].columns) and not found_ref: 
                                            found_ref = False
                                        else:
                                            found_ref = True
                                            self.std_out('Reference presence check passed')
                                if not found_ref: return False
            
            self.std_out('All checks passed')
            return True

    def run(self):
        
        # Process task by task
        for task in self.tasks.keys():
            self.std_out('Evaluating task {}'.format(task))

            if 'model' in self.tasks[task].keys():
                model_name = self.tasks[task]['model']['model_name'] 
                
                # Create model_wrapper instance
                self.std_out('Task {} involves modeling, initialising model'.format(task))
                current_model = model_wrapper(self.tasks[task]['model'],  
                                            verbose = self.verbose)
                
                # Parse current model instance
                has_model = True

                # Ignore extra data in json if present in the task
                if 'data' in self.tasks[task].keys(): self.std_out('Ignoring additional data in task')

                # Model dataset names
                tests = list(set(itertools.chain(self.tasks[task]['model']['data']['train'], self.tasks[task]['model']['data']['test'])))

            else:
                self.std_out('No model involved in task {}'.format(task))
                # Model dataset names
                tests = list(self.tasks[task]['data'])
                has_model = False


            # Cosmetic output
            self.std_out('Loading data...')

            # Load data
            if not self.load_data(tests, self.tasks[task]['options']):
                self.std_out('Failed loading data')
                return

            # Cosmetic output
            self.std_out('Sanity checks...')
            # Perform sanity check
            if not self.sanity_checks(self.tasks[task], tests, has_model):
                self.std_out('Failed sanity checks')
                return
                               
            # Pre-process data
            if 'pre-processing' in self.tasks[task].keys():
                # Cosmetic output
                self.std_out('Pre-processing needed...')

                if not self.pre_process_data(self.tasks[task], tests): 
                    self.std_out('Failed preprocessing')
                    return
            
            # Perform model stuff
            if has_model:
                # Prepare dataframe for training
                train_dataset = list(current_model.data['train'].keys())[0]

                if not self.records.prepare_dataframe_model(train_dataset, current_model.data['features'], 
                                                            current_model.data['train'][train_dataset], 
                                                            current_model.data['reference_device'], 
                                                            min_date = None, max_date = None, model_name = model_name):
                    self.std_out('Failed training dataset dataframe preparation for model')
                    return
                
                # Train Model based on training dataset
                current_model.training(self.records.readings[train_dataset]['models'][model_name])

                # Evaluate Model in train data
                device = current_model.data['train'][train_dataset]
                # Dirty horrible workaround
                if type(device) == list: device = device[0]
                prediction_name = device + '_' + model_name
                self.std_out('Predicting {} for device {} in {}'.format(prediction_name, device, train_dataset))
                # Get prediction for train
                prediction = current_model.predict_channels(self.records.readings[train_dataset]['devices'][device]['data'], prediction_name)
                # Combine it in readings
                self.records.readings[train_dataset]['devices'][device]['data'].combine_first(prediction)

                # Evaluate Model in test data
                for test_dataset in current_model.data['test'].keys():
                    for device in current_model.data['test'][test_dataset]:
                        prediction_name = device + '_' + model_name
                        self.std_out('Predicting {} for device {} in {}'.format(prediction_name, device, test_dataset))
                        # Get prediction for test
                        prediction = current_model.predict_channels(self.records.readings[test_dataset]['devices'][device]['data'], prediction_name)
                        # Combine it in readings
                        self.records.readings[test_dataset]['devices'][device]['data'].combine_first(prediction)

        
                # Export model data if requested
                if self.tasks[task]['options']['export_data']:
                    dataFrameExport = current_model.dataFrameTrain.copy()
                    dataFrameExport = dataFrameExport.combine_first(current_model.dataFrameTest)
                else:
                    dataFrameExport = None
                
                # Save model in session
                if current_model.options['session_active_model']:
                    self.std_out ('Saving model in session records...')
                    self.records.archive_model(dataset_name, current_model.name, current_model.type, current_model.metrics, 
                                        current_model.hyperparameters, current_model.options, dataFrameExport, current_model.model)

                # Export model if requested
                if current_model.options['export_model']:
                    current_model.export(self.records.modelDirectory)
                

            # Check export options
            optionExport = self.tasks[task]['options']['export_data']
            if optionExport != "None":
                if optionExport == 'Only Processed':
                    all_channels = False
                    processed_only = True
                elif optionExport == 'Only Generic':
                    all_channels = False
                    processed_only = False
                elif optionExport == 'All':
                    all_channels = True
                    processed_only = False

                # Export data to disk once tasks completed
                if has_model:
                    # Do it for both, train and test, if they exist
                    for dataset in ['train', 'test']:
                        # Check for datasets that are not reference
                        if dataset in self.tasks[task]['model']['data'].keys():
                            for test in self.tasks[task]['model']['data'][dataset].keys():
                                for device in self.tasks[task]['model']['data'][dataset][test]:
                                    self.std_out('Exporting data of device {} in test {} to processed folder'.format(device, test))
                                    self.records.export_data(test, device, all_channels = all_channels, 
                                                        hide_raw = processed_only, rename = self.tasks[task]['options'], to_processed_folder = True, 
                                                        forced_overwrite = True)
                else:
                    for test in self.tasks[task]['data'].keys():
                        for device in self.tasks[task]['data'][test]:
                            self.std_out('Exporting data of device {} in test {} to processed folder'.format(device, test))
                            self.records.export_data(test, device, all_channels = all_channels, 
                                hide_raw = processed_only, rename = self.tasks[task]['options'], to_processed_folder = True, 
                                forced_overwrite = True)
