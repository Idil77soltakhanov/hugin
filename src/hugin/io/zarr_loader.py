from .dataset_loaders import ArrayLoader
from dask.array import from_zarr, Array
from tensorflow.keras.utils import Sequence


def _data_generator(source_array, batch_size : int):
    yield None

class ArrayDataGenerator(object):
    def __init__(self, input_component_mapping: dict, output_component_mapping: dict, batch_size: int):
        self.input_component_mapping = input_component_mapping
        self.output_component_mapping = output_component_mapping
        self.batch_size = batch_size if batch_size is not None else 1
        self._index_iterator = self.__get_batch_indexes()

    def __get_batch_indexes(self):
        while True:
            total_entries = len(self)
            number_of_batches = total_entries // self.batch_size
            remainder = total_entries % self.batch_size
            for batch_idx in range(0, number_of_batches):
                batch_start_idx = batch_idx*self.batch_size
                batch_end_idx = batch_start_idx + self.batch_size
                yield (batch_start_idx, batch_end_idx)
            if remainder > 0:
                yield (batch_end_idx, total_entries)

    def get_input_shapes(self):
        shapes = {}
        for key, value in self.input_component_mapping.items():
            shapes[key] = value.shape[1:]
        return shapes

    def __len__(self):
        one_array = self.input_component_mapping[list(self.input_component_mapping.keys())[0]]
        return len(one_array)

    def __next__(self):
        return self.next()

    def next(self):
        start_index, end_index = next(self._index_iterator)
        inputs = {}
        outputs = {}
        for key, value in self.input_component_mapping.items():
            inputs[key] = value[start_index:end_index, ...]
        for key, value in self.output_component_mapping.items():
            pass
        return (inputs, outputs)

class ArraySequence(Sequence):
    def __init__(self, input_component_mapping: dict, output_component_mapping: dict, batch_size: int):
        self.input_component_mapping = input_component_mapping
        self.output_component_mapping = output_component_mapping
        self.batch_size = batch_size if batch_size is not None else 1

    def __len__(self):
        one_array = self.input_component_mapping[list(self.input_component_mapping.keys())[0]]
        return len(one_array)

    def __getitem__(self, idx):
        inputs = {}
        outputs = {}

        for key, value in self.input_component_mapping.items():
            inputs[key] = value[idx * self.batch_size:(idx + 1) * self.batch_size]
        for key, value in self.output_component_mapping.items():
            outputs[key] = value[idx * self.batch_size:(idx + 1) * self.batch_size]

        return (inputs, outputs)


    def get_input_shapes(self):
        shapes = {}
        for key, value in self.input_component_mapping.items():
            shapes[key] = value.shape[1:]
        return shapes


class ZarrArrayLoader(ArrayLoader):
    def __init__(self, source, inputs: dict, targets: dict, split_test_index_array: Array = None, split_train_index_array: Array = None):
        super(ZarrArrayLoader, self).__init__()
        self.inputs = {}
        self.split_test_index_array_path = split_test_index_array
        self.split_train_index_array_path = split_train_index_array
        self.split_test_index_array = None
        self.split_train_index_array = None
        if self.split_test_index_array_path:
            self.split_test_index_array = from_zarr(source, component=self.split_test_index_array_path)
        if self.split_train_index_array_path:
            self.split_train_index_array = from_zarr(source, component=self.split_test_index_array_path)

        for input_name, input_path in inputs.items():
            shape = None
            if isinstance(input_path, (tuple, list)):
                input_path, shape = input_path
            self.inputs[input_name] = from_zarr(source, component=input_path)
            if shape is not None:
                self.inputs[input_name] = self.inputs[input_name].reshape(shape)
        self.outputs = {}
        for output_name, output_path in targets.items():
            shape = None
            if isinstance(output_path, (tuple, list)) :
                output_path, shape = output_path
            self.outputs[output_name] = from_zarr(source, component=output_path)
            if shape is not None:
                outer_dimension = self.outputs[output_name].shape[0]
                self.outputs[output_name] = self.outputs[output_name].reshape((outer_dimension,) + tuple(shape))


    def get_training(self, batch_size : int) -> _data_generator:

        if self.split_train_index_array is not None:
            inputs = { k:v[self.split_train_index_array] for k,v in self.inputs.items()}
            outputs = {k: v[self.split_train_index_array] for k, v in self.outputs.items()}
        else:
            inputs = self.inputs
            outputs = self.outputs
        return ArraySequence(inputs, outputs, batch_size)

    def get_validation(self, batch_size : int) -> _data_generator:
        if self.split_test_index_array is None:
            return None

        if self.split_test_index_array is not None:
            inputs = { k:v[self.split_test_index_array] for k,v in self.inputs.items()}
            outputs = {k: v[self.split_test_index_array] for k, v in self.outputs.items()}

        return ArraySequence(inputs, outputs, batch_size)

    def get_mask(self):
        raise NotImplementedError()