import tensorflow as tf
from tensor_genn import TGModel
from tensor_genn.norm import DataNorm, SpikeNorm
from tensor_genn.utils import parse_arguments, raster_plot

class SimpleCNN(TGModel):
    def __init__(self, x_train, y_train, dt=1.0, input_type='poisson', rate_factor=1.0, rng_seed=0):
        super(SimpleCNN, self).__init__()

        # Define TensorFlow model
        tf_model = tf.keras.models.Sequential([
            tf.keras.layers.Conv2D(16, 5, padding='valid', activation='relu', use_bias=False, input_shape=x_train.shape[1:]),
            tf.keras.layers.AveragePooling2D(2),
            tf.keras.layers.Conv2D(8, 5, padding='same', activation='relu', use_bias=False),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(128, activation='relu', use_bias=False),
            tf.keras.layers.Dense(64, activation='relu', use_bias=False),
            tf.keras.layers.Dense(y_train.shape[0], activation='softmax', use_bias=False)
        ], name='simple_cnn')

        # Train and convert model
        tf_model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        tf_model.fit(x_train, y_train, epochs=5)
        self.convert_tf_model(tf_model, dt=dt, input_type=input_type, rate_factor=rate_factor, rng_seed=rng_seed)

if __name__ == '__main__':
    args = parse_arguments('Simple CNN classifier model')

    # Retrieve, reshape and normalise MNIST dataset
    (x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
    x_train = x_train[:args.n_train_samples].reshape((-1, 28, 28, 1)) / 255.0
    y_train = y_train[:args.n_train_samples]
    x_test = x_test[:args.n_test_samples].reshape((-1, 28, 28, 1)) / 255.0
    y_test = y_test[:args.n_test_samples]
    x_norm = x_train[:args.n_norm_samples]

    # Create, normalise and evaluate TensorGeNN model
    tg_model = SimpleCNN(x_train, y_train, dt=args.dt, input_type=args.input_type,
                         rate_factor=args.rate_factor, rng_seed=args.rng_seed)
    tg_model.tf_model.evaluate(x_test, y_test)
    if args.norm_method == 'data-norm':
        norm.normalize(tg_model)
        norm = DataNorm(x_norm, batch_size=None)
    elif args.norm_method == 'spike-norm':
        norm = SpikeNorm(x_norm, classify_time=args.classify_time, classify_spikes=args.classify_spikes)
        norm.normalize(tg_model)
    acc, spk_i, spk_t = tg_model.evaluate(x_test, y_test,
                                          classify_time=args.classify_time,
                                          classify_spikes=args.classify_spikes,
                                          save_samples=args.save_samples)

    # Report TensorGeNN model results
    print('Accuracy of SimpleCNN GeNN model on MNIST dataset: {}%'.format(acc))
    if args.plot:
        names = ['input_nrn'] + [name + '_nrn' for name in tg_model.layer_names]
        neurons = [tg_model.g_model.neuron_populations[name] for name in names]
        raster_plot(spk_i, spk_t, neurons)