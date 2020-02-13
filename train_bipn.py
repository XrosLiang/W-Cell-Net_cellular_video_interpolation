import os
import pickle
import numpy as np
import argparse
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import tensorflow as tf
from tensorflow.contrib import summary

from data_pipeline.read_record import read_and_decode
from models.utils.optimizer import get_optimizer
from models.utils.optimizer import count_parameters
from models import bipn


def training(args):
    
    # DIRECTORY FOR CKPTS and META FILES
    ROOT_DIR = '/neuhaus/movie/dataset/tf_records'
    TRAIN_REC_PATH = os.path.join(
        ROOT_DIR,
        args.experiment_name,
        'train.tfrecords')
    VAL_REC_PATH = os.path.join(
        ROOT_DIR,
        args.experiment_name,
        'val.tfrecords')
    CKPT_PATH = os.path.join(
        ROOT_DIR,
        args.experiment_name,
        'runs/')

    # SCOPING BEGINS HERE
    with tf.Session().as_default() as sess:
        global_step = tf.train.get_global_step()

        train_queue = tf.train.string_input_producer(
            [TRAIN_REC_PATH], num_epochs=None)
        train_fFrames, train_lFrames, train_iFrames, train_mfn =\
            read_and_decode(
                filename_queue=train_queue,
                is_training=True)

        val_queue = tf.train.string_input_producer(
            [VAL_REC_PATH], num_epochs=None)
        val_fFrames, val_lFrames, val_iFrames, val_mfn = \
            read_and_decode(
                filename_queue=val_queue,
                is_training=False)

        with tf.variable_scope('bipn'):
            print('TRAIN FRAMES (first):')
            train_rec_iFrames = bipn.build_bipn(
                train_fFrames,
                train_lFrames,
                use_batch_norm=True,
                is_training=True)

        with tf.variable_scope('bipn', reuse=tf.AUTO_REUSE):
            print('VAL FRAMES (first):')
            val_rec_iFrames = bipn.build_bipn(
                val_fFrames,
                val_lFrames,
                use_batch_norm=True,
                is_training=False)
            
        print('Model parameters:{}'.format(
            count_parameters()))

        # DEFINE METRICS
        train_reconstruction = train_iFrames - train_rec_iFrames
        train_l2_loss = tf.nn.l2_loss(
            train_reconstruction)
        val_reconstruction = val_iFrames - val_rec_iFrames
        val_l2_loss = tf.nn.l2_loss(
            val_reconstruction)

        # SUMMARIES
        tf.summary.scalar('train_l2_loss', train_l2_loss)
        tf.summary.scalar('val_l2_loss', val_l2_loss)
        # PROJECT IMAGES as well?
        merged = tf.summary.merge_all()
        train_writer = tf.summary.FileWriter(
            CKPT_PATH + 'train',
            sess.graph)

        # DEFINE OPTIMIZER
        optimizer = get_optimizer(
            train_loss,
            optim_id=args.optim_id,
            learning_rate=args.learning_rate,
            use_batch_norm=True)

        init_op = tf.group(
            tf.global_variables_initializer(),
            tf.local_variables_initializer())
        saver = tf.train.Saver()

        sess.run(init_op)

        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(
            coord=coord)

        # START TRAINING HERE
        try:
            for iteration in range(args.train_iter):
                _, t_summary, train_loss = sess.run(
                    [train_op, merged, train_l2_loss])
                train_writer.add_summary(t_summary, i)
                print('Iter:{}, Train Loss:{}'.format(
                    iteration,
                    train_loss))

                if iteration % args.val_every == 0:
                    val_loss = sess.run(val_l2_loss)
                    print('Iter:{}, Val Loss:{}'.format(
                        iteration,
                        val_loss))

                if iteration % args.save_every == 0:
                    saver.save(
                        sess,
                        CKPT_PATH + 'iter:{}_val:{}'.format(
                            str(iteration),
                            str(round(val_loss, 3))))

            coord.join(threads)

        except Exception as e:
            coord.request_stop(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='params of running the experiment')

    parser.add_argument(
        '--train_iter',
        type=int,
        default=10000,
        help='Mention the number of training iterations')

    parser.add_argument(
        '--val_every',
        type=int,
        default=100,
        help='Number of iterations after which validation is done')

    parser.add_argument(
        '--save_every',
        type=int,
        default=50,
        help='Number of iterations after which model is saved')
    parser.add_argument(
        '--experiment_name',
        type=str,
        default='slack_20px_fluorescent_window_5',
        help='to mention the experiment folder in tf_records')

    parser.add_argument(
        '--optim_id',
        type=int,
        default=1,
        help='ID to specify the learning rate to be used')

    parser.add_argument(
        '--learning_rate',
        type=float,
        default=1e-3,
        help='To mention the starting learning rate')

    args = parser.parse_args()

    training(args)
