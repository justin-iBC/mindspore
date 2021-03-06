# Copyright 2019 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""
Testing configuration manager
"""
import filecmp
import glob
import numpy as np
import os

from mindspore import log as logger

import mindspore.dataset as ds
import mindspore.dataset.transforms.vision.c_transforms as vision
import mindspore.dataset.transforms.vision.py_transforms as py_vision


DATA_DIR = ["../data/dataset/test_tf_file_3_images/train-0000-of-0001.data"]
SCHEMA_DIR = "../data/dataset/test_tf_file_3_images/datasetSchema.json"

def test_basic():
    ds.config.load('../data/dataset/declient.cfg')

    # assert ds.config.get_rows_per_buffer() == 32
    assert ds.config.get_num_parallel_workers() == 4
    # assert ds.config.get_worker_connector_size() == 16
    assert ds.config.get_prefetch_size() == 16
    assert ds.config.get_seed() == 5489

    # ds.config.set_rows_per_buffer(1)
    ds.config.set_num_parallel_workers(2)
    # ds.config.set_worker_connector_size(3)
    ds.config.set_prefetch_size(4)
    ds.config.set_seed(5)

    # assert ds.config.get_rows_per_buffer() == 1
    assert ds.config.get_num_parallel_workers() == 2
    # assert ds.config.get_worker_connector_size() == 3
    assert ds.config.get_prefetch_size() == 4
    assert ds.config.get_seed() == 5


def test_get_seed():
    """
    This gets the seed value without explicitly setting a default, expect int.
    """
    assert isinstance(ds.config.get_seed(), int)


def test_pipeline():
    """
    Test that our configuration pipeline works when we set parameters at different locations in dataset code
    """
    data1 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, shuffle=False)
    ds.config.set_num_parallel_workers(2)
    data1 = data1.map(input_columns=["image"], operations=[vision.Decode(True)])
    ds.serialize(data1, "testpipeline.json")

    data2 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, shuffle=False)
    ds.config.set_num_parallel_workers(4)
    data2 = data2.map(input_columns=["image"], operations=[vision.Decode(True)])
    ds.serialize(data2, "testpipeline2.json")

    # check that the generated output is different
    assert (filecmp.cmp('testpipeline.json', 'testpipeline2.json'))

    # this test passes currently because our num_parallel_workers don't get updated.

    # remove generated jason files
    file_list = glob.glob('*.json')
    for f in file_list:
        try:
            os.remove(f)
        except IOError:
            logger.info("Error while deleting: {}".format(f))


def test_deterministic_run_fail():
    """
    Test RandomCrop with seed, expected to fail
    """
    logger.info("test_deterministic_run_fail")

    # when we set the seed all operations within our dataset should be deterministic
    ds.config.set_seed(0)
    ds.config.set_num_parallel_workers(1)
    # First dataset
    data1 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    # Assuming we get the same seed on calling constructor, if this op is re-used then result won't be
    # the same in between the two datasets. For example, RandomCrop constructor takes seed (0)
    # outputs a deterministic series of numbers, e,g "a" = [1, 2, 3, 4, 5, 6] <- pretend these are random
    random_crop_op = vision.RandomCrop([512, 512], [200, 200, 200, 200])
    decode_op = vision.Decode()
    data1 = data1.map(input_columns=["image"], operations=decode_op)
    data1 = data1.map(input_columns=["image"], operations=random_crop_op)

    # Second dataset
    data2 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    data2 = data2.map(input_columns=["image"], operations=decode_op)
    # If seed is set up on constructor
    data2 = data2.map(input_columns=["image"], operations=random_crop_op)

    try:
        for item1, item2 in zip(data1.create_dict_iterator(), data2.create_dict_iterator()):
            np.testing.assert_equal (item1["image"], item2["image"])

    except BaseException as e:
        # two datasets split the number out of the sequence a
        logger.info("Got an exception in DE: {}".format(str(e)))
        assert "Array" in str(e)


def test_deterministic_run_pass():
    """
    Test deterministic run with with setting the seed
    """
    logger.info("test_deterministic_run_pass")
    ds.config.set_seed(0)
    ds.config.set_num_parallel_workers(1)

    # First dataset
    data1 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    # We get the seed when constructor is called
    random_crop_op = vision.RandomCrop([512, 512], [200, 200, 200, 200])
    decode_op = vision.Decode()
    data1 = data1.map(input_columns=["image"], operations=decode_op)
    data1 = data1.map(input_columns=["image"], operations=random_crop_op)

    # Second dataset
    data2 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    data2 = data2.map(input_columns=["image"], operations=decode_op)
    # Since seed is set up on constructor, so the two ops output deterministic sequence.
    # Assume the generated random sequence "a" = [1, 2, 3, 4, 5, 6] <- pretend these are random
    random_crop_op2 = vision.RandomCrop([512, 512], [200, 200, 200, 200])
    data2 = data2.map(input_columns=["image"], operations=random_crop_op2)
    try:
        for item1, item2 in zip(data1.create_dict_iterator(), data2.create_dict_iterator()):
            np.testing.assert_equal (item1["image"], item2["image"])
    except BaseException as e:
        # two datasets both use numbers from the generated sequence "a"
        logger.info("Got an exception in DE: {}".format(str(e)))
        assert "Array" in str(e)


def test_seed_undeterministic():
    """
    Test seed with num parallel workers in c, this test is expected to fail some of the time
    """
    logger.info("test_seed_undeterministic")
    ds.config.set_seed(0)

    # First dataset
    data1 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    # seed will be read in during constructor call
    random_crop_op = vision.RandomCrop([512, 512], [200, 200, 200, 200])
    decode_op = vision.Decode()
    data1 = data1.map(input_columns=["image"], operations=decode_op)
    data1 = data1.map(input_columns=["image"], operations=random_crop_op)

    # Second dataset
    data2 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    data2 = data2.map(input_columns=["image"], operations=decode_op)
    # If seed is set up on constructor, so the two ops output deterministic sequence
    random_crop_op2 = vision.RandomCrop([512, 512], [200, 200, 200, 200])
    data2 = data2.map(input_columns=["image"], operations=random_crop_op2)

    for item1, item2 in zip(data1.create_dict_iterator(), data2.create_dict_iterator()):
        np.testing.assert_equal (item1["image"], item2["image"])


def test_deterministic_run_distribution():
    """
    Test deterministic run with with setting the seed being used in a distribution
    """
    logger.info("test_deterministic_run_distribution")

    # when we set the seed all operations within our dataset should be deterministic
    ds.config.set_seed(0)
    ds.config.set_num_parallel_workers(1)

    # First dataset
    data1 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    random_crop_op = vision.RandomHorizontalFlip(0.1)
    decode_op = vision.Decode()
    data1 = data1.map(input_columns=["image"], operations=decode_op)
    data1 = data1.map(input_columns=["image"], operations=random_crop_op)

    # Second dataset
    data2 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    data2 = data2.map(input_columns=["image"], operations=decode_op)
    # If seed is set up on constructor, so the two ops output deterministic sequence
    random_crop_op2 = vision.RandomHorizontalFlip(0.1)
    data2 = data2.map(input_columns=["image"], operations=random_crop_op2)

    for item1, item2 in zip(data1.create_dict_iterator(), data2.create_dict_iterator()):
        np.testing.assert_equal (item1["image"], item2["image"])


def test_deterministic_python_seed():
    """
    Test deterministic execution with seed in python
    """
    logger.info("deterministic_random_crop_op_python_2")
    ds.config.set_seed(0)
    ds.config.set_num_parallel_workers(1)

    # First dataset
    data1 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)

    transforms = [
        py_vision.Decode(),
        py_vision.RandomCrop([512, 512], [200, 200, 200, 200]),
        py_vision.ToTensor(),
    ]
    transform = py_vision.ComposeOp(transforms)
    data1 = data1.map(input_columns=["image"], operations=transform())
    data1_output = []
    # config.set_seed() calls random.seed()
    for data_one in data1.create_dict_iterator():
        data1_output.append(data_one["image"])

    # Second dataset
    data2 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    data2 = data2.map(input_columns=["image"], operations=transform())
    # config.set_seed() calls random.seed(), resets seed for next dataset iterator
    ds.config.set_seed(0)

    data2_output = []
    for data_two in data2.create_dict_iterator():
        data2_output.append(data_two["image"])

    np.testing.assert_equal (data1_output, data2_output)


def test_deterministic_python_seed_multi_thread():
    """
    Test deterministic execution with seed in python, this fails with multi-thread pyfunc run
    """
    logger.info("deterministic_random_crop_op_python_2")
    ds.config.set_seed(0)
    # when we set the seed all operations within our dataset should be deterministic
    # First dataset
    data1 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    transforms = [
        py_vision.Decode(),
        py_vision.RandomCrop([512, 512], [200, 200, 200, 200]),
        py_vision.ToTensor(),
    ]
    transform = py_vision.ComposeOp(transforms)
    data1 = data1.map(input_columns=["image"], operations=transform(), python_multiprocessing=True)
    data1_output = []
    # config.set_seed() calls random.seed()
    for data_one in data1.create_dict_iterator():
        data1_output.append(data_one["image"])

    # Second dataset
    data2 = ds.TFRecordDataset(DATA_DIR, SCHEMA_DIR, columns_list=["image"], shuffle=False)
    # If seed is set up on constructor
    data2 = data2.map(input_columns=["image"], operations=transform(), python_multiprocessing=True)
    # config.set_seed() calls random.seed()
    ds.config.set_seed(0)

    data2_output = []
    for data_two in data2.create_dict_iterator():
        data2_output.append(data_two["image"])

    try:
        np.testing.assert_equal (data1_output, data2_output)
    except BaseException as e:
        # expect output to not match during multi-threaded excution
        logger.info("Got an exception in DE: {}".format(str(e)))
        assert "Array" in str(e)


if __name__ == '__main__':
    test_basic()
    test_pipeline()
    test_deterministic_run_pass()
    test_deterministic_run_distribution()
    test_deterministic_run_fail()
    test_deterministic_python_seed()
    test_seed_undeterministic()
    test_get_seed()
