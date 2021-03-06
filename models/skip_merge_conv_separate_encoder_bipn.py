import tensorflow as tf

from utils.layer import linear as MLP
from utils.layer import conv_batchnorm_relu as CBR
from utils.layer import upconv_2D as UC
from utils.layer import maxpool as MxP
from utils.layer import avgpool as AvP

def conv_block(inputs, block_name='block_1',
                out_channels=16,
                kernel_size=3,
                stride=1,
                use_batch_norm=False,
                is_training=False):

    get_shape = inputs.get_shape().as_list()

    with tf.variable_scope(block_name):
        conv_1 = CBR(
            inputs, 'conv_1', out_channels,
            activation=tf.keras.activations.relu,
            kernel_size=kernel_size, stride=stride,
            is_training=is_training,
            use_batch_norm=use_batch_norm)

        conv_2 = CBR(
            conv_1, 'conv_2', out_channels*2,
            activation=tf.keras.activations.relu,
            kernel_size=kernel_size, stride=stride,
            is_training=is_training,
            use_batch_norm=use_batch_norm)

    return conv_2
 

def encoder(inputs, use_batch_norm=False,
            is_training=False, is_verbose=False):

    layer_dict = {}

    get_shape = inputs.get_shape().as_list()
    if is_verbose: print('Inputs:{}'.format(get_shape))

    encode_1 = conv_block(
        inputs, block_name='block_1',
        out_channels=8, kernel_size=3,
        stride=1,
        use_batch_norm=use_batch_norm,
        is_training=is_training)
    encode_1 = MxP(
        encode_1,
        'MxP_1',
        [1, 2, 2, 1],
        [1, 2, 2, 1],
        padding='SAME')
    if is_verbose: print('Encode_1:{}'.format(encode_1))
    layer_dict['encode_1'] = encode_1

    encode_2 = conv_block(
        encode_1, block_name='block_2',
        out_channels=16, kernel_size=3,
        stride=1,
        use_batch_norm=use_batch_norm,
        is_training=is_training)
    encode_2 = MxP(
        encode_2,
        'MxP_2',
        [1, 2, 2, 1],
        [1, 2, 2, 1],
        padding='SAME')
    if is_verbose: print('Encode_2:{}'.format(encode_2))
    layer_dict['encode_2'] = encode_2

    encode_3 = conv_block(
        encode_2, block_name='block_3',
        out_channels=32, kernel_size=3,
        stride=1,
        use_batch_norm=use_batch_norm,
        is_training=is_training)
    encode_3 = MxP(
        encode_3,
        'MxP_3',
        [1, 2, 2, 1],
        [1, 2, 2, 1],
        padding='VALID')
    if is_verbose: print('Encode_3:{}'.format(encode_3))
    layer_dict['encode_3'] = encode_3

    encode_4 = conv_block(
        encode_3, block_name='block_4',
        out_channels=64, kernel_size=3,
        stride=1,
        use_batch_norm=use_batch_norm,
        is_training=is_training)
    encode_4 = MxP(
        encode_4,
        'MxP_4',
        [1, 2, 2, 1],
        [1, 2, 2, 1],
        padding='SAME')
    if is_verbose: print('Encode_4:{}'.format(encode_4))
    layer_dict['encode_4'] = encode_4

    return encode_4, layer_dict

def upconv_block(inputs, fFrames_encode,
                    lFrames_encode, merge=False,
                    block_name='block_1',
                    use_batch_norm=False,
                    kernel_size=3, stride=1,
                    use_bias=False,
                    is_training=False):

    # upconv(x2, c/2) --> 2 convs
    get_shape = inputs.get_shape().as_list()
    out_channels = get_shape[-1]

    with tf.variable_scope(block_name):
        net = UC(inputs, 'up_conv', out_channels//2,
            kernel_size=(2, 2), strides=(2, 2),
            use_bias=use_bias)

        if block_name == 'block_2':
            # BILINEAR RESIZE
            net = tf.image.resize_images(
                net, (25, 25),
                align_corners=True)

        if merge:
            # skip connection
            net = tf.concat(
                [
                    fFrames_encode,
                    net,
                    tf.reverse(
                        lFrames_encode,
                        axis=[-1])],
                axis=-1)

        get_shape = net.get_shape().as_list()
        out_channels = get_shape[-1]

        for i in range(2): 
            net = CBR(
                net, 'conv_{}'.format(str(i)), out_channels,
                activation=tf.keras.activations.tanh, # tanh
                kernel_size=kernel_size, stride=stride,
                is_training=is_training,
                use_batch_norm=use_batch_norm)

    return net


def decoder(inputs, layer_dict_fFrames,
            layer_dict_lFrames, use_batch_norm=False,
            out_channels=16, n_IF=3,
            is_training=False, is_verbose=False):

    get_shape = inputs.get_shape().as_list()

    decode_1 = upconv_block(
        inputs,
        layer_dict_fFrames['encode_3'],
        layer_dict_lFrames['encode_3'],
        merge=True,
        block_name='block_1',
        use_batch_norm=True,
        kernel_size=3, stride=1,
        use_bias=True)
    if is_verbose: print('Decode_1:{}'.format(decode_1))

    decode_2 = upconv_block(
        decode_1,
        layer_dict_fFrames['encode_2'],
        layer_dict_lFrames['encode_2'],
        merge=True,
        block_name='block_2',
        use_batch_norm=True,
        kernel_size=3, stride=1,
        use_bias=True)
    if is_verbose: print('Decode_2:{}'.format(decode_2))

    decode_3 = upconv_block(
        decode_2,
        layer_dict_fFrames['encode_1'],
        layer_dict_lFrames['encode_1'],
        merge=True,
        block_name='block_3',
        use_batch_norm=True,
        kernel_size=3, stride=1,
        use_bias=True)
    if is_verbose: print('Decode_3:{}'.format(decode_3))

    decode_4 = upconv_block(
        decode_3,
        None, None,
        merge=False,
        block_name='block_4',
        use_batch_norm=True,
        kernel_size=3, stride=1,
        use_bias=True)
    if is_verbose: print('Decode_4:{}'.format(decode_4))

    output = CBR(
        decode_4, 'conv_1', n_IF,
        activation=tf.keras.activations.tanh,
        kernel_size=3, stride=1,
        is_training=is_training,
        use_batch_norm=use_batch_norm)
    if is_verbose: print('Final Output:{}'.format(output))
               
    return output 


def build_bipn(fFrames, lFrames, use_batch_norm=False,
                is_training=False):

    with tf.variable_scope('encoder_1'):
        encode_fFrames, layer_dict_fFrames = encoder(
            fFrames,
            use_batch_norm=use_batch_norm,
            is_training=is_training,
            is_verbose=True)

    # use same encoder weights for last frame
    with tf.variable_scope('encoder_2'):
        encode_lFrames, layer_dict_lFrames = encoder(
            lFrames,
            use_batch_norm=use_batch_norm,
            is_training=is_training,
            is_verbose=False)

    # Flip :encode_lFrames
    # not too confident about tf.reverse behavior
    encode_lFrames = tf.reverse(
        encode_lFrames,
        axis=[-1])

    # Concatenate :encode_fFrames and :encode_lFrames
    encode_Frames = tf.concat(
        [encode_fFrames, encode_lFrames],
        axis=-1)
    print('Concatenated:{}'.format(
        encode_Frames.get_shape().as_list()))

    with tf.variable_scope('decoder'):
        rec_iFrames = decoder(
            encode_Frames,
            layer_dict_fFrames,
            layer_dict_lFrames,
            use_batch_norm=use_batch_norm,
            is_training=is_training,
            is_verbose=True)

    rec_iFrames = tf.transpose(
        rec_iFrames,
        [0, 3, 1, 2])
    rec_iFrames = tf.expand_dims(
        rec_iFrames,
        axis=-1)
    print('Final decoder:{}'.format(rec_iFrames))

    return rec_iFrames
