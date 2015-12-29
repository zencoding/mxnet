# pylint: skip-file
import numpy as np
import mxnet as mx
from numpy.testing import assert_allclose
from check_utils import (check_numeric_gradient, check_symbolic_backward,
                         check_symbolic_forward, reldiff)

def same(a, b):
    return np.sum(a != b) == 0

def check_elementwise_sum_with_shape(shape, n):
    # forward
    inputs = [mx.symbol.Variable('arg%d' % i) for i in range(n)]
    out = mx.symbol.ElementWiseSum(*inputs, name='esum')
    arr = [mx.nd.empty(shape) for i in range(n)]
    arr_grad = [mx.nd.empty(shape) for i in range(n)]
    for i in range(n):
        arr[i][:] = np.random.uniform(-10, 10, shape)
    exec1 = out.bind(mx.Context('cpu'),
                     args=arr,
                     args_grad=arr_grad)
    out1 = exec1.outputs[0].asnumpy()
    exec1.forward()
    out1 = exec1.outputs[0].asnumpy()
    out = sum(a.asnumpy() for a  in arr)
    assert reldiff(out, out1) < 1e-6
    out_grad = mx.nd.empty(shape)
    out_grad[:] = np.random.uniform(-10, 10, shape)
    # backward
    exec1.backward([out_grad])
    for a in arr_grad:
        assert same(a.asnumpy(), out_grad.asnumpy())

def test_elementwise_sum():
    np.random.seed(0)
    nrepeat = 2
    maxdim = 4
    for repeat in range(nrepeat):
        for dim in range(1, maxdim):
            shape = tuple(np.random.randint(1, int(1000**(1.0/dim)), size=dim))
            check_elementwise_sum_with_shape(shape, np.random.randint(1, 8))

def check_slice_channel(dim, num):
    ins = []
    if dim == 2:
        shape = (2,2)
    else:
        shape = (2, 2, 2 ,3)
    ins = [np.ones(shape) * i for i in range(num)]
    e = np.hstack(ins)

    e_nd = mx.nd.empty(e.shape)
    e_nd[:] = e
    data = mx.sym.Variable('data')
    op = mx.sym.SliceChannel(data=data, num_outputs=num)
    arg_shape, output_shape, aux_shape = op.infer_shape(data=e_nd.shape)
    grad_nd = [mx.nd.empty(shape) for shape in arg_shape]

    exe = op.bind(mx.cpu(), args=[e_nd], args_grad=grad_nd)
    assert len(exe.outputs) == num
    o_nd = [exe.outputs[i] for i in range(num)]
    # test forward
    exe.forward()
    for i in range(num):
        assert reldiff(o_nd[i].asnumpy(), ins[i]) < 1e-5
    # test backward
    for i in range(num):
        o_nd[i] += i
    exe.backward(o_nd)
    assert reldiff(grad_nd[0].asnumpy(), np.hstack([ins[i] + i for i in range(num)])) < 1e-5

def check_concat_with_shape(shapes, dimension):
    n = len(shapes)
    # forward
    target_dim = 0
    for shape in shapes:
        target_dim += shape[dimension]

    inputs = [mx.symbol.Variable('arg%d' % i) for i in range(n)]
    out = mx.symbol.Concat(*inputs, name='conc',dim=dimension)
    arr = [mx.nd.empty(shape) for shape in shapes]
    for i in range(n):
        arr[i][:] = shapes[i][dimension]
    arr_np = [np.copy(narray.asnumpy()) for narray in arr]
    arr_grad = [mx.nd.empty(shape) for shape in shapes]
    args = out.list_arguments()
    arg_shapes, out_shapes, aux_shapes = out.infer_shape(**dict(zip(args, shapes)))
    out_grad = mx.nd.empty(out_shapes[0])
    exec1 = out.bind(mx.Context('cpu'),
                     args=arr,
                     args_grad=arr_grad)
    exec1.forward()
    out1 = exec1.outputs[0]
    ret = np.concatenate([narray.asnumpy() for narray in arr], axis=dimension)
    assert same(out1.asnumpy(), ret)
    # backward
    out1.copyto(out_grad)
    out_grad[:] += 1
    exec1.backward([out_grad])
    for grad, np_grad in zip(arr_grad, arr_np):
        assert same(grad.asnumpy(), np_grad + 1)

def test_concat():
    for dimension in range(4):
        n = 2
        merge = [2, 3, 4, 5, 6]
        a = 2
        b = 3
        c = 4
        # test  2D
        if dimension<2:
            for dim in range(2, 6):
                shapes = []
                for i in range(dim):
                    if dimension == 0:
                        shapes.append((merge[i], a))
                    elif dimension == 1:
                        shapes.append((a, merge[i]))
                    check_concat_with_shape(shapes,dimension)
        #test 3D
        if dimension<3:
            for dim in range(2, 6):
                shapes = []
                for i in range(dim):
                    if dimension == 0:
                        shapes.append((merge[i], a,b))
                    elif dimension ==1:
                        shapes.append((a,merge[i],b))
                    elif dimension ==2:
                        shapes.append((a,b,merge[i]))
                check_concat_with_shape(shapes,dimension)
        # test 4D
        for dim in range(2, 6):
            shapes = []
            for i in range(dim):
                if dimension == 0:
                    shapes.append((merge[i],a,b,c))
                elif dimension == 1:
                    shapes.append((a,merge[i],b,c))
                elif dimension ==2:
                    shapes.append((a,b,merge[i],c))
                elif dimension ==3:
                    shapes.append((a,b,c,merge[i]))
            check_concat_with_shape(shapes,dimension)

def test_slice_channel():
    check_slice_channel(2, 4)
    check_slice_channel(4, 4)
    check_slice_channel(2, 16)

def check_regression(symbol, forward, backward):
    data = mx.symbol.Variable('data')
    label = mx.symbol.Variable('label')
    out = symbol(data, label)
    shape = (3, 1)
    arr_data = mx.random.uniform(-1, 1, shape)
    arr_label = mx.random.uniform(0, 1, shape[0])
    arr_grad = mx.nd.empty(shape)
    exec1 = out.bind(mx.cpu(),
                     args=[arr_data, arr_label],
                     args_grad={"data" : arr_grad})
    exec1.forward()
    out1 = exec1.outputs[0].asnumpy()
    npout = forward(arr_data.asnumpy())
    assert reldiff(npout, out1) < 1e-6

    exec1.backward()
    npout = backward(npout,  arr_label.asnumpy().reshape(npout.shape))
    assert reldiff(npout, arr_grad.asnumpy()) < 1e-6

def test_regression():
    check_regression(mx.symbol.LogisticRegressionOutput,
                     lambda x: 1.0 / (1.0 + np.exp(-x)),
                     lambda x, y : x - y)
    check_regression(mx.symbol.LinearRegressionOutput,
                     lambda x: x,
                     lambda x, y : x - y)

def check_softmax_with_shape(shape, xpu):
    X = mx.symbol.Variable('X')
    L = mx.symbol.Variable('L')
    Y = mx.symbol.Softmax(data=X, label=L)
    x = mx.random.uniform(-1, 1, shape, ctx = xpu)
    l = mx.nd.empty((shape[0],), ctx = xpu)
    l[:] = np.random.randint(0, shape[0]-1, (shape[0],))
    grad = mx.nd.empty(shape, ctx = xpu)

    exec1 = Y.bind(xpu, args = [x, l], args_grad = {'X': grad})
    print('foward')
    exec1.forward()
    print(exec1.outputs[0].asnumpy())
    exec1.backward()
    print(grad.asnumpy())

def check_multi_softmax_with_shape(shape, xpu):
    X = mx.symbol.Variable('X')
    L = mx.symbol.Variable('L')
    Y = mx.symbol.Softmax(data=X, label=L, multi_output=True)
    x = mx.random.uniform(-1, 1, shape, ctx = xpu)
    l = mx.nd.empty((shape[0], shape[2]), ctx = xpu)
    l[:] = np.random.randint(0, shape[1]-1, (shape[0], shape[2]))
    grad = mx.nd.empty(shape, ctx = xpu)

    exec1 = Y.bind(xpu, args = [x, l], args_grad = {'X': grad})
    exec1.forward()
    print(exec1.outputs[0].asnumpy())
    exec1.backward()
    print(grad.asnumpy())

def test_python_op():
    X = mx.symbol.Variable('X')
    op = mx.operator.NumpyOp()
    s = op.get_symbol(X, name='numpy_op')

    x = mx.ndarray.ones((10))*10
    dx = mx.ndarray.zeros((10))
    dy = mx.ndarray.ones((10))
    exec1 = s.bind(mx.cpu(), args=[x], args_grad = {'X': dx})
    exec1.forward()
    assert reldiff(x.asnumpy(), exec1.outputs[0].asnumpy()) < 1e-5
    exec1.backward(dy)
    assert reldiff(dy.asnumpy(), dx.asnumpy()) < 1e-5

def test_swapaxes():
    data = mx.symbol.Variable('data')
    shape = (2, 3, 4)
    data_tmp = np.ones(shape)
    data_tmp[0] = 1
    data_tmp[1] = 2
    arr_data = mx.nd.array(data_tmp)
    swap0 = mx.symbol.SwapAxis(data=data, dim1=0, dim2=2)
    swap = mx.symbol.SwapAxis(data=swap0, dim1=1, dim2=2)
    exe_c = swap.bind(mx.cpu(), args=[arr_data])
    exe_c.forward()
    out = exe_c.outputs[0].asnumpy()

    swap0_ = np.swapaxes(data_tmp, 0, 2)
    swap_ = np.swapaxes(swap0_, 1, 2)

    assert reldiff(out, swap_) < 1e-6

def test_scalarop():
    data = mx.symbol.Variable('data')
    shape = (3, 4)
    data_tmp = np.ones(shape)*5
    arr_data = mx.nd.array(data_tmp)
    arr_grad = mx.nd.empty(shape)
    arr_grad[:]=3

    test = 2 / (4-((1+data+1)*2/5)-0.2)

    npout_1 = (4-((1+data_tmp+1)*2/5)-0.2)
    npout = 2/npout_1

    check_symbolic_forward(test, [data_tmp], [npout])

    npout_grad = 2.*2/5
    npout_grad = 2*npout_grad /(npout_1 *npout_1 )

    check_symbolic_backward(test, [data_tmp], [np.ones(shape)*2], [npout_grad])


def test_scalar_pow():
    data = mx.symbol.Variable('data')
    shape = (1, 1)
    data_tmp = np.ones(shape)
    test = data ** 2
    check_numeric_gradient(test, [data_tmp])
    check_symbolic_forward(test, [data_tmp], [data_tmp ** 2])
    check_symbolic_backward(test, [data_tmp], [np.ones(shape)], [2 * data_tmp])

def test_symbol_pow():
    shape = (1, 1)

    data = mx.symbol.Variable('data')
    data_tmp = np.ones(shape)*2

    exp = mx.symbol.Variable('exp')
    exp_tmp = np.ones(shape)*3

    test = data**exp

    check_numeric_gradient(test, [data_tmp, exp_tmp])
    check_symbolic_forward(test, [data_tmp, exp_tmp], [data_tmp**exp_tmp])

    data_dir = data_tmp**(exp_tmp - 1) * exp_tmp
    exp_dir = data_tmp**(exp_tmp) * np.log(data_tmp)
    check_symbolic_backward(test, [data_tmp, exp_tmp], [np.ones(shape)], [data_dir, exp_dir])

def test_pow_fn():
    shape = (3, 4)
    exp = mx.symbol.Variable("exp")
    y = mx.sym.pow(2, exp)
    x = np.ones(shape)*3
    check_numeric_gradient(y, [x])
    check_symbolic_forward(y, [x], [2**x])
    check_symbolic_backward(y, [x], [np.ones(shape)], [np.log(2) * 2**x])

def test_embedding():
    in_dim = 10
    out_dim = 4
    batch = 24

    data = mx.sym.Variable("data")
    embed = mx.sym.Embedding(data=data, input_dim=in_dim, output_dim=out_dim, name="embed")
    exe_test = embed.simple_bind(mx.cpu(), data=(batch,))
    arg_map = dict(zip(embed.list_arguments(), exe_test.arg_arrays))
    grad_map = dict(zip(embed.list_arguments(), exe_test.grad_arrays))
    np_data = np.random.randint(low=0, high=in_dim, size=batch)
    np_weight = np.random.uniform(-0.01, 0.01, arg_map["embed_weight"].shape)
    np_onehot = np.zeros((batch, in_dim))
    np_onehot[np.arange(batch), np_data] = 1.0
    # forward
    arg_map["data"][:] = np_data
    arg_map["embed_weight"][:] = np_weight
    exe_test.forward()
    assert reldiff(exe_test.outputs[0].asnumpy(), np.dot(np_onehot, np_weight)) < 1e-6
    # backward
    np_grad = np.random.uniform(-1, 1, exe_test.outputs[0].shape)
    grad = mx.nd.zeros(np_grad.shape)
    grad[:] = np_grad
    exe_test.backward([grad])
    assert reldiff(grad_map["embed_weight"].asnumpy(), np.dot(np_onehot.T, np_grad)) < 1e-6

# check ops handle duplicate input correctly.
def test_binary_op_duplicate_input():
    data = mx.symbol.Variable('data')
    shape = (3, 4)
    data_tmp = np.ones(shape)
    data_tmp[:] = 5
    arr_data = mx.nd.array(data_tmp)
    arr_grad = mx.nd.empty(shape)
    arr_grad[:] = 3
    out_grad = mx.nd.empty(shape)
    out_grad[:] = 1
    square = data * data
    exe_square = square.bind(mx.cpu(), args=[arr_data], args_grad=[arr_grad])
    exe_square.forward()
    assert reldiff(exe_square.outputs[0].asnumpy(), data_tmp * data_tmp) < 1e-6
    exe_square.backward(out_grad)
    assert reldiff(arr_grad.asnumpy(), 2.0 * data_tmp) < 1e-6

def test_sign():
    data = mx.symbol.Variable('data')
    shape = (3, 4)
    data_tmp = np.ones(shape)
    data_tmp[:]=5
    arr_data = mx.nd.array(data_tmp)
    arr_grad = mx.nd.empty(shape)
    arr_grad[:]=3

    test = mx.sym.sign(data)
    exe_test = test.bind(mx.cpu(), args=[arr_data], args_grad=[arr_grad])
    exe_test.forward()
    out = exe_test.outputs[0].asnumpy()
    npout = np.sign(data_tmp)
    assert reldiff(out, npout) < 1e-6

    out_grad = mx.nd.empty(shape)
    out_grad[:] = 2;
    npout_grad = out_grad.asnumpy()
    npout_grad = 0;
    exe_test.backward(out_grad)
    assert reldiff(arr_grad.asnumpy(), npout_grad) < 1e-6

def test_round_ceil_floor():
    data = mx.symbol.Variable('data')
    shape = (3, 4)
    data_tmp = np.ones(shape)
    data_tmp[:]=5.543
    arr_data = mx.nd.array(data_tmp)
    arr_grad = mx.nd.empty(shape)
    arr_grad[:]= 2

    test = mx.sym.round(data) + mx.sym.ceil(data) +  mx.sym.floor(data)
    exe_test = test.bind(mx.cpu(), args=[arr_data])
    exe_test.forward()
    out = exe_test.outputs[0].asnumpy()
    npout = np.round(data_tmp) + np.ceil(data_tmp) + np.floor(data_tmp)
    assert reldiff(out, npout) < 1e-6

def test_rsqrt_cos_sin():
    data = mx.symbol.Variable('data')
    shape = (3, 4)
    data_tmp = np.ones(shape)
    data_tmp[:]=5
    arr_data = mx.nd.array(data_tmp)
    arr_grad = mx.nd.empty(shape)
    arr_grad[:]=3

    test =  mx.sym.rsqrt(data) + mx.sym.cos(data) + mx.sym.sin(data)
    exe_test = test.bind(mx.cpu(), args=[arr_data], args_grad=[arr_grad])
    exe_test.forward()
    out = exe_test.outputs[0].asnumpy()
    npout =  1/ np.sqrt(data_tmp) + np.cos(data_tmp) + np.sin(data_tmp)
    assert reldiff(out, npout) < 1e-6

    out_grad = mx.nd.empty(shape)
    out_grad[:] = 2;
    npout_grad = out_grad.asnumpy()
    npout_grad = npout_grad * -(1.0 / (2.0 * data_tmp * np.sqrt(data_tmp))) + npout_grad * -1 * np.sin(data_tmp) + npout_grad * np.cos(data_tmp)
    exe_test.backward(out_grad)
    assert reldiff(arr_grad.asnumpy(), npout_grad) < 1e-6

def test_maximum_minimum():
    data1 = mx.symbol.Variable('data')
    data2 = mx.symbol.Variable('data')
    shape = (3, 4)
    data_tmp1 = np.random.rand(3,4)
    data_tmp2 = np.random.rand(3,4)
    data_tmp1[:] = 2
    data_tmp2[:] = 3
    
    arr_data1 = mx.nd.array(data_tmp1)
    arr_data2 = mx.nd.array(data_tmp2)

    
    arr_grad1 = mx.nd.empty(shape)
    arr_grad2 = mx.nd.empty(shape)


    test =  mx.sym.maximum(data1,data2) + mx.sym.minimum(data1,data2);
    exe_test = test.bind(mx.cpu(), args=[arr_data1,arr_data2], args_grad=[arr_grad1,arr_grad2])
    exe_test.forward()
    out = exe_test.outputs[0].asnumpy()
    npout =  np.maximum(data_tmp1,data_tmp2) + np.minimum(data_tmp1,data_tmp2)
    assert reldiff(out, npout) < 1e-6

    out_grad = mx.nd.empty(shape)
    out_grad[:] = 2
    exe_test.backward(out_grad)
    
    npout_grad = np.ones(shape)
    npout_grad[:] = 2
    mask1 = (data_tmp1 > data_tmp2).astype('float')
    mask2 = (data_tmp1 < data_tmp2).astype('float')
    npout_grad1 = npout_grad * mask1 + npout_grad * mask2
    npout_grad2 = (npout_grad - npout_grad * mask1) + (npout_grad - npout_grad * mask2)
    
    assert reldiff(arr_grad1.asnumpy(), npout_grad1) < 1e-6
    assert reldiff(arr_grad2.asnumpy(), npout_grad2) < 1e-6

def test_maximum_minimum_scalar():
    data1 = mx.symbol.Variable('data')
    shape = (3, 4)
    data_tmp1 = np.random.rand(3,4)
    data_tmp1[:] = 2
 
    arr_data1 = mx.nd.array(data_tmp1)
    arr_grad1 = mx.nd.empty(shape)

    test =  mx.sym.maximum(data1,3) + mx.sym.maximum(9,data1) + mx.sym.minimum(5,data1) + mx.sym.minimum(data1,4)
    exe_test = test.bind(mx.cpu(), args=[arr_data1], args_grad=[arr_grad1])
    exe_test.forward()
    out = exe_test.outputs[0].asnumpy()
    npout =  np.maximum(data_tmp1,3) + np.maximum(9,data_tmp1) + np.minimum(5,data_tmp1) + np.minimum(data_tmp1,4)
    assert reldiff(out, npout) < 1e-6

    out_grad = mx.nd.empty(shape)
    out_grad[:] = 2
    exe_test.backward(out_grad)
    
    npout_grad = np.ones(shape)
    npout_grad[:] = 2
    mask1 = (data_tmp1 > 3).astype('float')
    mask2 = (9 > data_tmp1).astype('float')
    mask3 = (5 < data_tmp1).astype('float')
    mask4 = (data_tmp1 < 4).astype('float')
    npout_grad1 = npout_grad * mask1 + (npout_grad - npout_grad * mask2) + (npout_grad - npout_grad * mask3) + npout_grad * mask4
    
    assert reldiff(arr_grad1.asnumpy(), npout_grad1) < 1e-6

def test_abs():
    data = mx.symbol.Variable('data')
    shape = (3, 4)
    data_tmp = np.ones(shape)
    data_tmp[:]=5
    arr_data = mx.nd.array(data_tmp)
    arr_grad = mx.nd.empty(shape)
    arr_grad[:]=3

    test = mx.sym.abs(data)
    exe_test = test.bind(mx.cpu(), args=[arr_data], args_grad=[arr_grad])
    exe_test.forward()
    out = exe_test.outputs[0].asnumpy()
    npout = abs(data_tmp)
    assert reldiff(out, npout) < 1e-6

    out_grad = mx.nd.empty(shape)
    out_grad[:] = 2;
    npout_grad = out_grad.asnumpy()
    npout_grad = npout_grad * np.sign(data_tmp)
    exe_test.backward(out_grad)
    assert reldiff(arr_grad.asnumpy(), npout_grad) < 1e-6

def check_deconvolution_forward_backward(input_shape, num_filter, kernel, stride, pad):
    """configure A: input --> conv --> deconv --> output.
       the convolution and deconvoluiton has similar parameter which ensure
       the input shape is the same as output, and the same weights between conv
       and deconv;
       If the input value of forward() and backwrad() is the same, then
       the output value of them should also the same;
    """
    assert input_shape[1] == num_filter
    data = mx.sym.Variable(name="data")
    conv = mx.sym.Convolution(
        data=data, kernel=kernel, stride=stride, pad=pad,
        num_filter=num_filter, no_bias = "true", name = "conv")
    deconv = mx.sym.Deconvolution(
        data=conv, kernel=kernel, stride=stride, pad=pad,
        num_filter=num_filter, no_bias = "true", name = "deconv")

    arg_names = deconv.list_arguments()
    arg_shapes, out_shapes, _ = deconv.infer_shape(data=input_shape)
    input_data = mx.random.uniform(-5, 5, input_shape)
    out_grad = input_data
    args = {}
    args["data"] = input_data
    args['conv_weight'] = args['deconv_weight'] = mx.random.normal(0, 1,
        (num_filter, input_shape[1]) + kernel)
    args_grad = [mx.nd.empty(s) for s in arg_shapes]

    exe = deconv.bind(mx.cpu(), args=args, args_grad=args_grad)
    exe.forward()
    out = exe.outputs[0].asnumpy()
    exe.backward(out_grad)
    assert reldiff(out, args_grad[0].asnumpy()) < 1e-6

def check_deconvolution_gradient(input_shape, num_filter, pad):
    """configure A: input --> conv --> output.
       configure B: input --> deconv --> output
       the convolution and deconvoluiton has similar parameter which ensure
       the input shape is the same as output;
       During backward(), if the input of A equals output of B, and the output
       of A equals input of B, then the grad of weight should be the same;
    """
    stride = (1, 1)
    kernel = (2*pad[0]+1, 2*pad[1]+1)
    data_conv = mx.sym.Variable(name="data_conv")
    conv = mx.sym.Convolution(
        data=data_conv, kernel=kernel, stride=stride, pad=pad,
        num_filter=num_filter, no_bias = "true", name = "conv")
    data_deconv = mx.sym.Variable(name="data_deconv")
    deconv = mx.sym.Deconvolution(
        data=data_deconv, kernel=kernel, stride=stride, pad=pad,
        num_filter=num_filter, no_bias = "true", name = "deconv")

    conv_data = mx.random.uniform(-5, 5, input_shape)
    conv_args = {}
    conv_args["data_conv"] = conv_data
    conv_args['conv_weight'] = \
        mx.random.normal(0, 1,(num_filter, input_shape[1]) + kernel)
    conv_args_grad = [mx.nd.zeros(conv_data.shape),
        mx.nd.zeros((num_filter, input_shape[1]) + kernel)]
    exe_conv = conv.bind(mx.cpu(), args=conv_args, args_grad=conv_args_grad)
    conv_out_grad = mx.random.normal(0, 2, exe_conv.outputs[0].shape)
    exe_conv.backward(conv_out_grad)

    deconv_data = conv_out_grad
    deconv_args = {}
    deconv_args['data_deconv'] = deconv_data
    deconv_args['deconv_weight'] = conv_args['conv_weight']
    deconv_args_grad = [mx.nd.zeros(deconv_data.shape),
        mx.nd.zeros((num_filter, input_shape[1]) + kernel)]
    exe_deconv = deconv.bind(mx.cpu(), args=deconv_args, args_grad=deconv_args_grad)
    deconv_out_grad = conv_data[:]
    exe_deconv.backward(deconv_out_grad)
    assert reldiff(conv_args_grad[1].asnumpy(), deconv_args_grad[1].asnumpy()) < 1e-6

def test_deconvolution():
    check_deconvolution_forward_backward(
        input_shape         = (1,1,5,5),
        num_filter          = 1,
        kernel              = (3,3),
        stride              = (1,1),
        pad                 = (1,1)
    )
    check_deconvolution_forward_backward(
        input_shape         = (32,3,28,28),
        num_filter          = 3,
        kernel              = (3,3),
        stride              = (1,1),
        pad                 = (1,1)
    )
    check_deconvolution_forward_backward(
        input_shape         = (10, 3, 403, 403),
        num_filter          = 3,
        kernel              = (7,7),
        stride              = (5,5),
        pad                 = (2,2)
    )
    check_deconvolution_gradient(
        input_shape = (1,3,5,5),
        num_filter = 3,
        pad = (1,1)
    )
    check_deconvolution_gradient(
        input_shape = (5,3,100,100),
        num_filter = 3,
        pad = (3,3)
    )

def check_nearest_upsampling_with_shape(shapes, scale, root_scale):
    arr = {'arg_%d'%i: mx.random.uniform(-10.0, 10.0, shape) for i, shape in zip(range(len(shapes)), shapes)}
    arr_grad = {'arg_%d'%i: mx.nd.zeros(shape) for i, shape in zip(range(len(shapes)), shapes)}

    up = mx.sym.UpSampling(*[mx.sym.Variable('arg_%d'%i) for i in range(len(shapes))], sample_type='nearest', scale=root_scale)
    exe = up.bind(mx.cpu(), args=arr, args_grad=arr_grad)
    exe.forward(is_train=True)
    exe.backward(exe.outputs)
    for k in range(len(shapes)):
        name = 'arg_%d'%k
        assert_allclose(arr[name].asnumpy()*root_scale**2*scale**(2*k), arr_grad[name].asnumpy(), rtol=1e-4)


def test_nearest_upsampling():
    for root_scale in [1,2,3]:
        for scale in [1,2,3]:
            for num_shape in [1,2,3]:
                for base in [1,2,3]:
                    shapes = [(1,3,base*root_scale*scale**(num_shape-1-i),base*root_scale*scale**(num_shape-1-i)) for i in range(num_shape)]
                    check_nearest_upsampling_with_shape(shapes, scale, root_scale)

def test_batchnorm_training():
    for shape in [(2, 3), (2, 3, 2, 2)]:
        data_tmp = np.random.normal(size=shape)
        s = shape[1],
        gamma = np.ones(s)
        beta = np.ones(s)
        gamma[1] = 3
        beta[0] = 3

        rolling_mean = np.random.uniform(size=s)
        rolling_std = np.random.uniform(size=s)

        data = mx.symbol.Variable('data')
        test = mx.symbol.BatchNorm(data, fix_gamma=False)

        check_numeric_gradient(test, [data_tmp, gamma, beta], [rolling_mean, rolling_std], numeric_eps=1e-3, check_eps=5e-2)

        # Gamma needs to be fixed at one when fix_gamma is true,
        gamma = np.ones(s)

        test = mx.symbol.BatchNorm(data, fix_gamma=True)
        check_numeric_gradient(test, [data_tmp, gamma, beta], [rolling_mean, rolling_std], numeric_eps=1e-3, check_eps=5e-2)

if __name__ == '__main__':
    test_nearest_upsampling()
    test_binary_op_duplicate_input()
    test_elementwise_sum()
    test_concat()
    test_slice_channel()
    test_regression()
    test_python_op()
    test_swapaxes()
    test_scalarop();
    test_scalar_pow()
    test_symbol_pow()
    test_pow_fn()
    test_embedding()
    test_rsqrt_cos_sin()
    test_maximum_minimum()
    test_maximum_minimum_scalar()
    test_abs()
    test_round_ceil_floor()
    test_deconvolution()
    test_batchnorm_training()
    #check_softmax_with_shape((3,4), mx.cpu())
    #check_multi_softmax_with_shape((3,4,5), mx.cpu())
