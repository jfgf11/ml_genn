import pytest
import numpy as np
import tensorflow as tf
import tensor_genn as tg

def test_conv2d_1_in_chan_1_out_chan_1_stride_valid():

    # Kernel
    k = np.array([
        [0, 0, 1],
        [0, 1, 0],
        [1, 0, 0],
    ], dtype=np.float32)

    # Input
    x = np.array([
        [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
        [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
        [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1],
        [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
        [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
        [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    ], dtype=np.float32)

    # Target Output
    y = np.array([
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
        [2, 1, 1, 2, 1, 1, 2, 1, 1, 2],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 2, 1, 1, 2, 1, 1, 2, 1],
        [0, 2, 0, 0, 2, 0, 0, 2, 0, 0],
        [3, 0, 0, 3, 0, 0, 3, 0, 0, 3],
        [0, 1, 2, 1, 0, 3, 0, 1, 2, 1],
        [1, 2, 1, 1, 2, 1, 1, 2, 1, 1],
        [1, 2, 1, 2, 1, 2, 1, 2, 1, 2],
    ], dtype=np.float32)

    # Create TensorFlow model
    tf_model = tf.keras.models.Sequential([
        tf.keras.layers.Conv2D(1, 3, padding='valid', strides=1, activation='relu', use_bias=False, input_shape=(12, 12, 1)),
    ], name='test_conv2d_1_in_chan_1_out_chan_1_stride_valid')
    tf_k = k[:, :, np.newaxis, np.newaxis]
    tf_model.set_weights([tf_k])

    # Assert TensorFlow model is correct
    tf_x = x[np.newaxis, :, :, np.newaxis]
    tf_y = tf_model(tf_x).numpy()
    assert (tf_y[0, :, :, 0] == y).all()

    # Create Tensor GeNN model
    tg_model = tg.TGModel(tf_model)
    tg_model.create_genn_model(dt=1.0, input_type='if_cs')

    # Assert Tensor GeNN model is correct
    neurons = tg_model.g_model.neuron_populations['conv2d_nrn']
    neurons.extra_global_params['Vthr'].view[:] = y.max()


    for i in range(y.max()):

        pass


    #accuracy, _, _ = tg_model.evaluate_genn_model([x], [y], classify_time=y.max())


    print(tf_model.summary())


    print(accuracy)

    assert accuracy == 100.0


if __name__ == '__main__':
    test_conv2d_1_in_chan_1_out_chan_1_stride_valid()
