import pickle
import cv2
import numpy as np
import os
import random
import argparse

import tensorflow as tf
import resize

def get_data(IMAGE_DIR, window):
    '''Returns list of data points
    Args:
        IMAGE_DIR: 'String' that points to
            image directory
        window: 'Integer' to specify the
            size of the tuple
    Returns:
        'List' of data points sampled
    '''    
    data = []

    folders = os.listdir(
        IMAGE_DIR)

    for folder in folders:
        folder_path = os.path.join(
            IMAGE_DIR,
            folder)

        images = os.listdir(
            folder_path)

        images = sorted(images)
        images = [
            os.path.join(
                folder_path,
                image)
            for image in images]

        for i in range(len(images) - window):
            data.append(images[i : i + window])

    return data

def get_splits(data, val_split, test_split):
    '''Returns splits of data
    Args:
        data: 'List' of data samples
        val_split: 'Float' to mention the fraction of
            validation data
        test_split: 'Float' to mention the fraction of
            test data
    Returns:
        3 'List' variables containing the training,
        validation and testing samples
    '''
    train_split = 1.0 - (val_split + test_split)

    random.shuffle(data)
    dataLength = len(data)

    train_data = data[
        0 : int(dataLength * train_split)]

    val_data = data[
        int(dataLength * train_split) :\
        int(dataLength * (train_split + val_split))]

    test_data = data[
        int(dataLength * (train_split + val_split)):]

    return train_data, val_data, test_data

##### TF helper functions #####
def _bytes_feature(value):
    '''Returns serialized data
    Args:
        value: 'Tensor' containing data
    Returns:
        Serialized data
    '''
    return tf.train.Feature(
        bytes_list=tf.train.BytesList(
            value=[value]))

def feat_example(fFrame, lFrame, iFrames, metaFileNames):
    '''Computes TF examples
    Args:
        fFrame: 'Numpy' matrix of dtype np.float32 containing
            first frame data
        lFrame: 'Numpy' matrix of dtype  np.float32 containing
            last frame data
        iFrames: 'Numpy' matrix of dtype np.float32 containing
            intermediate frames data
        metaFileNames: 'String' that contains meta information
    '''
    assert fFrame.shape == (100, 100, 1), 'Error'
    assert lFrame.shape == (100, 100, 1), 'Error'
    assert iFrames.shape == (3, 100, 100, 1), 'Error'

    feature = {
        'data/first_frame': _bytes_feature(
            tf.compat.as_bytes(
                fFrame.tostring())),
        'data/last_frame': _bytes_feature(
            tf.compat.as_bytes(
                lFrame.tostring())),
        'data/intermediate_frames': _bytes_feature(
            tf.compat.as_bytes(
                iFrames.tostring())),
        'data/meta_file_names': _bytes_feature(
            tf.compat.as_bytes(
                metaFileNames))}

    example = tf.train.Example(
        features=tf.train.Features(
            feature=feature))

    return example

def read_image(filename):
    '''Returns np.float32 format image
    Args:
        filename: 'String' containing path to image
    Returns:
        'Numpy' grayscale image of dtype np.float32
    '''
    return cv2.imread(
        filename, 0)

def dump_pickle(filename, data):
    '''Dumps pickle file
    Args:
        filename: 'String' containing dump path
        data: 'Dict' containing data samples
    '''
    with open(filename, 'wb') as handle:
        pickle.dump(
            data,
            handle)

def write_tfr(TFR_DIR, data, targetHeight=100,
                targetWidth=100):
    '''Create TF Records
    Args:
        TFR_DIR: 'String' that points to directory
            where data will be written
        data: 'Dict' that stores samples
        targetHeight: 'Integer' to specify the height
            of each frame
        targetHeight: 'Integer' to specify the width
            of each frame
    '''
    writer = tf.python_io.TFRecordWriter(
        TFR_DIR)

    for tup_id in range(len(data)):
        tup = data[tup_id]
        metaFileNames = ', '.join(tup)
        fFrame, lFrame = tup[0], tup[-1]
        iFrames = tup[1: -1]
 
        fFrame = read_image(fFrame)
        lFrame = read_image(lFrame)
        
        fFrame = resize.pad_image(
            fFrame,
            targetHeight,
            targetWidth)
        lFrame = resize.pad_image(
            lFrame,
            targetHeight,
            targetWidth)

        # SANITY CHECK
        height, width = fFrame.shape
        assert height == targetHeight and\
            width == targetWidth,\
             'check {}'.format(
                metaFileNames)
        height, width = lFrame.shape
        assert height == targetHeight and\
            width == targetWidth,\
                'check {}'.format(
                metaFileNames)

        # Stack intermediate frames
        intermediateFrames = np.zeros(
            (len(iFrames), targetHeight, targetWidth),
            dtype=np.uint8)

        for frame_id in range(len(iFrames)):
            iFrame = read_image(
                iFrames[frame_id])
            iFrame = resize.pad_image(
                iFrame,
                targetHeight,
                targetWidth)
            intermediateFrames[frame_id] = iFrame

        fFrame = np.expand_dims(
            fFrame, axis=-1)
        lFrame = np.expand_dims(
            lFrame, axis=-1)
        intermediateFrames = np.expand_dims(
            intermediateFrames, axis=-1)
 
        example = feat_example(
            fFrame,
            lFrame,
            intermediateFrames,
            metaFileNames)

        writer.write(
            example.SerializeToString())
    
        if tup_id % 5000 == 0:
            print('Wrote {}/{} examples.....'.format(
                tup_id, len(data)))

    writer.close()


def control(args):
    '''Interface method
    Args:
        args: 'ArgumentParser' containing meta information
    ''' 
    TFR_DIR = os.path.join(
        args.TFR_DIR,
        'slack_20px_fluorescent_window_{}'.format(
            args.window))

    if not os.path.exists(TFR_DIR):
        os.makedirs(TFR_DIR)

    data = get_data(
        args.IMAGE_DIR,
        args.window)

    train_data, val_data, test_data = get_splits(
        data,
        args.VAL_SPLIT,
        args.TEST_SPLIT)

    # DUMP pickle files
    dump_pickle(
        TFR_DIR + '/train_meta_files.pkl',
        train_data)
    dump_pickle(
        TFR_DIR + '/validation_meta_files.pkl',
        val_data)
    dump_pickle(
        TFR_DIR + '/test_meta_files.pkl',
        test_data)
    print('Meta files dumped.....')

    # Write TF Records
    print('Splits created.....Writing TFRecords.....')
    print('Writing train TFR.....')
    write_tfr(
        TFR_DIR + '/train.tfrecords',
        train_data,
        targetHeight=100,
        targetWidth=100)
    print('Finished writing train TFR.....')
    print('Writing validation TFR.....')
    write_tfr(
        TFR_DIR + '/val.tfrecords',
        val_data,
        targetHeight=100,
        targetWidth=100)
    print('Finished writing validation TFR.....')
    print('Writing test TFR.....')
    write_tfr(
        TFR_DIR + '/test.tfrecords',
        test_data,
        targetHeight=100,
        targetWidth=100)
    print('Finished writing test TFR.....') 
    
   
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='params of running the experiment')

    parser.add_argument(
        '--IMAGE_DIR',
        type=str,
        default=os.path.join(
            '/neuhaus/movie/dataset',
            'slack_20px',
            'fluorescent'),
        help='path where images are present')

    parser.add_argument(
        '--window',
        type=int,
        default=5,
        help='mentions the number of frames in each\
            batch. 1 frame corresponds to 6 seconds')

    parser.add_argument(
        '--VAL_SPLIT',
        type=float,
        default=0.15,
        help='specifies the percentage of data to be\
            used for validation')

    parser.add_argument(
        '--TEST_SPLIT',
        type=float,
        default=0.15,
        help='specifies the percentage of data to be\
            used for testing')

    parser.add_argument(
        '--TFR_DIR',
        type=str,
        default=os.path.join(
            '/neuhaus/movie/dataset',
            'tf_records'),
        help='root path where TF Records will be saved')

    args = parser.parse_args()

    control(args)
