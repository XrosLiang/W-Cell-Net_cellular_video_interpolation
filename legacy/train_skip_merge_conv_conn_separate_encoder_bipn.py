import os
import pickle
import numpy as np
import argparse
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import tensorflow as tf
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
from tensorflow.contrib import summary

from data_pipeline.read_record import read_and_decode

from utils.optimizer import get_optimizer
from utils.optimizer import count_parameters
from utils.losses import huber_loss
from utils.losses import l2_loss
from utils.losses import ridge_weight_decay
from utils.visualizer import visualize_frames
from utils.visualizer import visualize_tensorboard

from models import skip_merge_conv_separate_encoder_bipn

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
        'skip_merge_conv_summary_image_tanh_separate_bipn_wd_l2_adam_1e-3/')

    # SCOPING BEGINS HERE
    with tf.Session().as_default() as sess:
        global_step = tf.train.get_global_step()

        train_queue = tf.train.string_input_producer(
            [TRAIN_REC_PATH], num_epochs=None)
        train_fFrames, train_lFrames, train_iFrames, train_mfn =\
            read_and_decode(
                filename_queue=train_queue,
                is_training=True,
                batch_size=args.batch_size)

        val_queue = tf.train.string_input_producer(
            [VAL_REC_PATH], num_epochs=None)
        val_fFrames, val_lFrames, val_iFrames, val_mfn = \
            read_and_decode(
                filename_queue=val_queue,
                is_training=False,
                batch_size=args.batch_size)

        with tf.variable_scope('separate_bipn'):
            print('TRAIN FRAMES (first):')
            train_rec_iFrames = skip_merge_conv_separate_encoder_bipn.build_bipn(
                train_fFrames,
                train_lFrames,
                use_batch_norm=True,
                is_training=True)

        with tf.variable_scope('separate_bipn', reuse=tf.AUTO_REUSE):
            print('VAL FRAMES (first):')
            val_rec_iFrames = skip_merge_conv_separate_encoder_bipn.build_bipn(
                val_fFrames,
                val_lFrames,
                use_batch_norm=True,
                is_training=False)
            
        print('Model parameters:{}'.format(
            count_parameters()))

        # DEFINE METRICS
        if args.loss_id == 0:
            train_loss = huber_loss(
                train_iFrames, train_rec_iFrames,
                delta=1.)
            val_loss = huber_loss(
                val_iFrames, val_rec_iFrames,
                delta=1.)

        elif args.loss_id == 1:
            train_loss = l2_loss(
                train_iFrames, train_rec_iFrames)
            val_loss = l2_loss(
                val_iFrames, val_rec_iFrames) 

        if args.weight_decay:
            decay_loss = ridge_weight_decay(
                tf.trainable_variables())
            train_loss += args.weight_decay * decay_loss

        # SUMMARIES
        tf.summary.scalar('train_loss', train_loss)
        tf.summary.scalar('val_loss', val_loss)

        with tf.contrib.summary.\
            record_summaries_every_n_global_steps(
                n=args.summary_image_every):
            summary_true, summary_fake = visualize_tensorboard(
                train_fFrames,
                train_lFrames,
                train_iFrames,
                train_rec_iFrames,
                num_plots=3)
            tf.summary.image('true frames', summary_true)
            tf.summary.image('fake frames', summary_fake)

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
            for iteration in range(args.train_iters):
                _, t_summ, t_loss = sess.run(
                    [optimizer, merged, train_loss])

                train_writer.add_summary(t_summ, iteration)
                print('Iter:{}/{}, Train Loss:{}'.format(
                    iteration,
                    args.train_iters,
                    t_loss))

                if iteration % args.val_every == 0:
                    v_loss = sess.run(val_loss)
                    print('Iter:{}, Val Loss:{}'.format(
                        iteration,
                        v_loss))

                if iteration % args.save_every == 0:
                    saver.save(
                        sess,
                        CKPT_PATH + 'iter:{}_val:{}'.format(
                            str(iteration),
                            str(round(v_loss, 3))))

                '''
                if iteration % args.plot_every == 0:
                    start_frames, end_frames, mid_frames,\
                        rec_mid_frames = sess.run(
                            [train_fFrames, train_lFrames,\
                                train_iFrames,\
                                train_rec_iFrames])

                    visualize_frames(
                        start_frames,
                        end_frames,
                        mid_frames,
                        rec_mid_frames,
                        iteration=iteration,
                        save_path=os.path.join(
                            CKPT_PATH,
                            'plots/'))
                '''

            coord.join(threads)

        except Exception as e:
            coord.request_stop(e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='params of running the experiment')

    parser.add_argument(
        '--train_iters',
        type=int,
        default=15000,
        help='Mention the number of training iterations')

    parser.add_argument(
        '--val_every',
        type=int,
        default=100,
        help='Number of iterations after which validation is done')

    parser.add_argument(
        '--save_every',
        type=int,
        default=100,
        help='Number of iterations after which model is saved')

    parser.add_argument(
        '--plot_every',
        type=int,
        default=1000,
        help='Number of iterations after which plots will be saved')

    parser.add_argument(
        '--summary_image_every',
        type=int,
        default=500,
        help='Number of iterations after which images will get pushed to tensorboard')

    parser.add_argument(
        '--experiment_name',
        type=str,
        default='slack_20px_fluorescent_window_5',
        help='to mention the experiment folder in tf_records')

    parser.add_argument(
        '--optim_id',
        type=int,
        default=1,
        help='1. adam, 2. SGD + momentum')

    parser.add_argument(
        '--learning_rate',
        type=float,
        default=1e-3,
        help='To mention the starting learning rate')

    parser.add_argument(
        '--batch_size',
        type=int,
        default=32,
        help='To mention the number of samples in a batch')

    parser.add_argument(
        '--loss_id',
        type=int,
        default=1,
        help='0:huber, 1:l2')

    parser.add_argument(
        '--weight_decay',
        type=float,
        default=0.01,
        help='To mention the strength of L2 weight decay')

    args = parser.parse_args()

    training(args)

