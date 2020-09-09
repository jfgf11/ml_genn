import numpy as np
from math import ceil
from pygenn.genn_model import create_custom_init_var_snippet_class
from pygenn.genn_model import init_var
from pygenn.genn_wrapper import NO_DELAY

from tensor_genn.layers import ConnectionType, PadMode
from tensor_genn.layers.base_connection import BaseConnection


avepool2d_conv2d_init = create_custom_init_var_snippet_class(
    'avepool2d_conv2d',

    param_names=[
        'pool_kh', 'pool_kw',
        'pool_sh', 'pool_sw',
        'pool_padh', 'pool_padw',
        'pool_ih', 'pool_iw', 'pool_ic',
        'conv_kh', 'conv_kw',
        'conv_sh', 'conv_sw',
        'conv_padh', 'conv_padw',
        'conv_ih', 'conv_iw', 'conv_ic',
        'conv_oh', 'conv_ow', 'conv_oc',
    ],

    extra_global_params=[
        ('kernels', 'scalar*'),
    ],

    var_init_code='''
    const int pool_kh = $(pool_kh), pool_kw = $(pool_kw);
    const int pool_sh = $(pool_sh), pool_sw = $(pool_sw);
    const int pool_padh = $(pool_padh), pool_padw = $(pool_padw);
    const int pool_ih = $(pool_ih), pool_iw = $(pool_iw), pool_ic = $(pool_ic);

    const int pool_in_row = ($(id_pre) / pool_ic) / pool_iw;
    const int pool_in_col = ($(id_pre) / pool_ic) % pool_iw;
    const int pool_in_chan = $(id_pre) % pool_ic;

    const int conv_kh = $(conv_kh), conv_kw = $(conv_kw);
    const int conv_sh = $(conv_sh), conv_sw = $(conv_sw);
    const int conv_padh = $(conv_padh), conv_padw = $(conv_padw);
    const int conv_ic = $(conv_ic);
    const int conv_ow = $(conv_ow), conv_oc = $(conv_oc);

    const int conv_out_row = ($(id_post) / conv_oc) / conv_ow;
    const int conv_out_col = ($(id_post) / conv_oc) % conv_ow;
    const int conv_out_chan = $(id_post) % conv_oc;

    int conv_stride_row = conv_out_row * conv_sh - conv_padh;
    int conv_stride_col = conv_out_col * conv_sw - conv_padw;

    scalar weight = 0.0;

    // process only strides with rows containing pool_in_row
    int pool_out_row = (pool_in_row + pool_padh) / pool_sh;
    int pool_stride_row = pool_out_row * pool_sh - pool_padh;
    while ((pool_stride_row >= -pool_padh) && (pool_stride_row + pool_kh > pool_in_row)) {

        int pool_kh_crop = min(pool_stride_row + pool_kh, pool_ih) - max(pool_stride_row, 0);

        // process only strides with cols containing pool_in_col
        int pool_out_col = (pool_in_col + pool_padw) / pool_sw;
        int pool_stride_col = pool_out_col * pool_sw - pool_padw;
        while ((pool_stride_col >= -pool_padw) && (pool_stride_col + pool_kw > pool_in_col)) {

            int pool_kw_crop = min(pool_stride_col + pool_kw, pool_iw) - max(pool_stride_col, 0);

            int conv_in_row = pool_out_row;
            int conv_in_col = pool_out_col;
            int conv_in_chan = pool_in_chan;

            int conv_k_row = conv_in_row - conv_stride_row;
            int conv_k_col = conv_in_col - conv_stride_col;

            if (conv_k_row >= 0 && conv_k_row < conv_kh && conv_k_col >= 0 && conv_k_col < conv_kw) {
                weight += $(kernels)[
                    conv_k_row * (conv_kw * conv_ic * conv_oc) +
                    conv_k_col * (conv_ic * conv_oc) +
                    conv_in_chan * (conv_oc) +
                    conv_out_chan
                ] / (pool_kh_crop * pool_kw_crop);
            }

            pool_out_col--;
            pool_stride_col = pool_out_col * pool_sw - pool_padw;
        }

        pool_out_row--;
        pool_stride_row = pool_out_row * pool_sh - pool_padh;
    }

    $(value) = weight;
    ''',
)


class AvePool2DConv2DConnection(BaseConnection):

    def __init__(self, filters, pool_size, conv_size, pool_strides=None, conv_strides=None,
                 pool_padding='valid', conv_padding='valid', connection_type='procedural'):
        super(AvePool2DConv2DConnection, self).__init__()
        self.filters = filters
        self.pool_size = pool_size
        self.conv_size = conv_size
        if pool_strides == None:
            self.pool_strides = (pool_size[0], pool_size[1])
        else:
            self.pool_strides = pool_strides
        if conv_strides == None:
            self.conv_strides = (1, 1)
        else:
            self.conv_strides = conv_strides
        self.pool_padding = PadMode(pool_padding)
        self.conv_padding = PadMode(conv_padding)
        self.pool_output_shape = None
        self.connection_type = ConnectionType(connection_type)


    def compile(self, tg_model):
        super(AvePool2DConv2DConnection, self).compile(tg_model)

        # Procedural initialisation
        if self.connection_type == ConnectionType.PROCEDURAL:
            pool_kh, pool_kw = self.pool_size
            pool_sh, pool_sw = self.pool_strides
            pool_ih, pool_iw, pool_ic = self.source.shape
            if self.pool_padding == PadMode.VALID:
                pool_padh = 0
                pool_padw = 0
            elif self.pool_padding == PadMode.SAME:
                pool_padh = (pool_kh - 1) // 2
                pool_padw = (pool_kw - 1) // 2

            conv_kh, conv_kw = self.conv_size
            conv_sh, conv_sw = self.conv_strides
            conv_ih, conv_iw, conv_ic = self.pool_output_shape
            conv_oh, conv_ow, conv_oc = self.target.shape
            if self.conv_padding == PadMode.VALID:
                conv_padh = 0
                conv_padw = 0
            elif self.conv_padding == PadMode.SAME:
                conv_padh = (conv_kh - 1) // 2
                conv_padw = (conv_kw - 1) // 2

            g = init_var(avepool2d_conv2d_init, {
                'pool_kh': pool_kh, 'pool_kw': pool_kw,
                'pool_sh': pool_sh, 'pool_sw': pool_sw,
                'pool_padh': pool_padh, 'pool_padw': pool_padw,
                'pool_ih': pool_ih, 'pool_iw': pool_iw, 'pool_ic': pool_ic,
                'conv_kh': conv_kh, 'conv_kw': conv_kw,
                'conv_sh': conv_sh, 'conv_sw': conv_sw,
                'conv_padh': conv_padh, 'conv_padw': conv_padw,
                'conv_ih': conv_ih, 'conv_iw': conv_iw, 'conv_ic': conv_ic,
                'conv_oh': conv_oh, 'conv_ow': conv_ow, 'conv_oc': conv_oc,
            })

        # Sparse initialisation
        elif self.connection_type == ConnectionType.SPARSE:
            g, indices = self.genn_sparse_weights()

        # Add batch synapse populations
        for batch_i in range(tg_model.batch_size):
            pre_nrn = self.source.nrn[batch_i]
            post_nrn = self.target.nrn[batch_i]
            syn_name = '{}_to_{}_syn_{}'.format(self.source.name, self.target.name, batch_i)

            # Batch master
            if not tg_model.share_weights or batch_i == 0:

                if self.connection_type == ConnectionType.PROCEDURAL:
                    self.syn[batch_i] = tg_model.g_model.add_synapse_population(
                        syn_name, 'DENSE_PROCEDURALG', NO_DELAY, pre_nrn, post_nrn,
                        'StaticPulse', {}, {'g': g}, {}, {}, 'DeltaCurr', {}, {}
                    )
                    self.syn[batch_i].vars['g'].set_extra_global_init_param('kernels', self.weights.flatten())

                elif self.connection_type == ConnectionType.SPARSE:
                    self.syn[batch_i] = tg_model.g_model.add_synapse_population(
                        syn_name, 'SPARSE_INDIVIDUALG', NO_DELAY, pre_nrn, post_nrn,
                        'StaticPulse', {}, {'g': g}, {}, {}, 'DeltaCurr', {}, {}
                    )
                    self.syn[batch_i].set_sparse_connections(indices[0], indices[1])

            # Batch slave
            else:
                master_syn_name = '{}_to_{}_syn_0'.format(self.source.name, self.target.name)
                self.syn[batch_i] = tg_model.g_model.add_slave_synapse_population(
                    syn_name, master_syn_name, NO_DELAY, pre_nrn, post_nrn, 'DeltaCurr', {}, {}
                )


    def connect(self, source, target):
        super(AvePool2DConv2DConnection, self).connect(source, target)

        pool_kh, pool_kw = self.pool_size
        pool_sh, pool_sw = self.pool_strides
        pool_ih, pool_iw, pool_ic = source.shape
        if self.pool_padding == PadMode.VALID:
            self.pool_output_shape = (
                ceil(float(pool_ih - pool_kh + 1) / float(pool_sh)),
                ceil(float(pool_iw - pool_kw + 1) / float(pool_sw)),
                pool_ic,
            )
        elif self.pool_padding == PadMode.SAME:
            self.pool_output_shape = (
                ceil(float(pool_ih) / float(pool_sh)),
                ceil(float(pool_iw) / float(pool_sw)),
                pool_ic,
            )

        conv_kh, conv_kw = self.conv_size
        conv_sh, conv_sw = self.conv_strides
        conv_ih, conv_iw, conv_ic = self.pool_output_shape
        if self.conv_padding == PadMode.VALID:
            self.output_shape = (
                ceil(float(conv_ih - conv_kh + 1) / float(conv_sh)),
                ceil(float(conv_iw - conv_kw + 1) / float(conv_sw)),
                self.filters,
            )
        elif self.conv_padding == PadMode.SAME:
            self.output_shape = (
                ceil(float(conv_ih) / float(conv_sh)),
                ceil(float(conv_iw) / float(conv_sw)),
                self.filters,
            )

        if target.shape is None:
            target.shape = self.output_shape
        elif self.output_shape != target.shape:
            raise RuntimeError('target layer shape mismatch')

        self.weights = np.empty((conv_kh, conv_kw, conv_ic, self.filters), dtype=np.float64)


    def genn_sparse_weights(self):

        # === AvePool2D Weights ===
        pool_weights = np.zeros((np.prod(self.source.shape), np.prod(self.pool_output_shape)))
        pool_connect = np.zeros(pool_weights.shape, dtype=np.bool)

        pool_kh, pool_kw = self.pool_size
        pool_sh, pool_sw = self.pool_strides
        pool_ih, pool_iw, pool_ic = self.source.shape
        pool_oh, pool_ow, pool_oc = self.pool_output_shape
        if self.pool_padding == PadMode.VALID:
            pool_padh = 0
            pool_padw = 0
        elif self.pool_padding == PadMode.SAME:
            pool_padh = (pool_kh - 1) // 2
            pool_padw = (pool_kw - 1) // 2

        # For each in {one-to-one input -> output channel}:
        for channel in range(pool_ic):
            pool_chan_weights = pool_weights[channel::pool_ic, channel::pool_oc]
            pool_chan_connect = pool_connect[channel::pool_ic, channel::pool_oc]

            # For each AvePool2D output pixel:
            for pool_out_row in range(pool_oh):
                pool_stride_row = pool_out_row * pool_sh - pool_padh
                for pool_out_col in range(pool_ow):
                    pool_stride_col = pool_out_col * pool_sw - pool_padw

                    # Get a weights view for this out pixel.
                    pool_out_pixel_weights = pool_chan_weights[:, pool_out_row * pool_ow + pool_out_col]
                    pool_out_pixel_weights.shape = (pool_ih, pool_iw)
                    pool_out_pixel_connect = pool_chan_connect[:, pool_out_row * pool_ow + pool_out_col]
                    pool_out_pixel_connect.shape = (pool_ih, pool_iw)

                    # Get a weights view for this cropped stride.
                    crop_T = max(pool_stride_row, 0)
                    crop_B = min(pool_stride_row + pool_kh, pool_ih)
                    crop_L = max(pool_stride_col, 0)
                    crop_R = min(pool_stride_col + pool_kw, pool_iw)
                    pool_stride_weights = pool_out_pixel_weights[crop_T:crop_B, crop_L:crop_R]
                    pool_stride_connect = pool_out_pixel_connect[crop_T:crop_B, crop_L:crop_R]

                    # Set weights for this stride.
                    pool_stride_weights[:] = 1.0 / pool_stride_weights.size
                    pool_stride_connect[:] = True

        # === Conv2D Weights ===
        conv_weights = np.zeros((np.prod(self.pool_output_shape), np.prod(self.target.shape)))
        conv_connect = np.zeros(conv_weights.shape, dtype=np.bool)

        conv_kh, conv_kw = self.conv_size
        conv_sh, conv_sw = self.conv_strides
        conv_ih, conv_iw, conv_ic = self.pool_output_shape
        conv_oh, conv_ow, conv_oc = self.target.shape
        if self.conv_padding == PadMode.VALID:
            conv_padh = 0
            conv_padw = 0
        elif self.conv_padding == PadMode.SAME:
            conv_padh = (conv_kh - 1) // 2
            conv_padw = (conv_kw - 1) // 2

        # For each in {all-to-all input -> output channel}:
        for in_channel in range(conv_ic):
            for out_channel in range(conv_oc):
                conv_chan_kernel = self.weights[:, :, in_channel, out_channel]
                conv_chan_weights = conv_weights[in_channel::conv_ic, out_channel::conv_oc]
                conv_chan_connect = conv_connect[in_channel::conv_ic, out_channel::conv_oc]

                # For each Conv2D output pixel: 
                for conv_out_row in range(conv_oh):
                    conv_stride_row = conv_out_row * conv_sh - conv_padh
                    for conv_out_col in range(conv_ow):
                        conv_stride_col = conv_out_col * conv_sw - conv_padw

                        # Get a weights view for this out pixel.
                        conv_out_pixel_weights = conv_chan_weights[:, conv_out_row * conv_ow + conv_out_col]
                        conv_out_pixel_weights.shape = (conv_ih, conv_iw)
                        conv_out_pixel_connect = conv_chan_connect[:, conv_out_row * conv_ow + conv_out_col]
                        conv_out_pixel_connect.shape = (conv_ih, conv_iw)

                        # Get a weights view for this cropped stride.
                        crop_T = max(conv_stride_row, 0)
                        crop_B = min(conv_stride_row + conv_kh, conv_ih)
                        crop_L = max(conv_stride_col, 0)
                        crop_R = min(conv_stride_col + conv_kw, conv_iw)
                        conv_stride_weights = conv_out_pixel_weights[crop_T:crop_B, crop_L:crop_R]
                        conv_stride_connect = conv_out_pixel_connect[crop_T:crop_B, crop_L:crop_R]

                        # Get a cropped kernel view.
                        crop_T =       0 - min(conv_stride_row, 0)
                        crop_B = conv_kh - max(conv_stride_row + conv_kh - conv_ih, 0)
                        crop_L =       0 - min(conv_stride_col, 0)
                        crop_R = conv_kw - max(conv_stride_col + conv_kw - conv_iw, 0)
                        conv_cropped_kernel = conv_chan_kernel[crop_T:crop_B, crop_L:crop_R]

                        # Set weights for this stride.
                        conv_stride_weights[:] = conv_cropped_kernel
                        conv_stride_connect[:] = True

        # === Combined Weights ===
        combined_weights = np.zeros((pool_weights.shape[0], conv_weights.shape[1]))
        combined_connect = np.zeros(combined_weights.shape, dtype=np.bool)

        # For each in {one-to-one input -> output channel}:
        for channel in range(pool_ic):
            pool_chan_weights = pool_weights[channel::pool_ic, channel::pool_ic]
            pool_chan_connect = pool_connect[channel::pool_ic, channel::pool_ic]
            conv_chan_weights = conv_weights[channel::pool_ic, :]
            conv_chan_connect = conv_connect[channel::pool_ic, :]
            combined_chan_weights = combined_weights[channel::pool_ic, :]
            combined_chan_connect = combined_connect[channel::pool_ic, :]

            # Set weights to dot product of AvePool2D and Conv2D weights.
            combined_chan_weights[:] = np.dot(pool_chan_weights, conv_chan_weights)
            combined_chan_connect[:] = np.dot(pool_chan_connect, conv_chan_connect)

        # === Weight Values and Indices ===
        w_indices = np.nonzero(combined_connect)
        w_values = combined_weights[w_indices]
        return w_values, w_indices
