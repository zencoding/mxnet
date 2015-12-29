/*!
 * Copyright (c) 2015 by Contributors
 * \file upsampling_nearest.cc
 * \brief
 * \author Bing Xu
*/

#include "./deconvolution-inl.h"
#include "./upsampling-inl.h"

namespace mxnet {
namespace op {
template<>
Operator *CreateOp<cpu>(UpSamplingParam param) {
  if (param.sample_type == up_enum::kNearest) {
    return new UpSamplingNearestOp<cpu>(param);
  } else if (param.sample_type == up_enum::kBilinear) {
    DeconvolutionParam p;
    int kernel = 2 * param.scale - param.scale % 2;
    int stride = param.scale;
    int pad = static_cast<int>(ceil((param.scale - 1) / 2.));
    p.num_group = param.num_filter;
    p.num_filter = param.num_filter;
    p.no_bias =  true;
    int shape[] = {1, 1};
    shape[0] = shape[1] = kernel;
    p.kernel = TShape(shape, shape + 2);
    shape[0] = shape[1] = stride;
    p.stride = TShape(shape, shape + 2);
    shape[0] = shape[1] = pad;
    p.pad = TShape(shape, shape + 2);
    return new DeconvolutionOp<cpu>(p);
  } else {
    LOG(FATAL) << "Unknown sample type";
    return NULL;
  }
}

Operator* UpSamplingProp::CreateOperator(Context ctx) const {
  DO_BIND_DISPATCH(CreateOp, param_);
}

DMLC_REGISTER_PARAMETER(UpSamplingParam);

MXNET_REGISTER_OP_PROPERTY(UpSampling, UpSamplingProp)
.describe("Perform nearest neighboor/bilinear up sampling to inputs")
.add_arguments(UpSamplingParam::__FIELDS__())
.set_key_var_num_args("num_args");
}  // namespace op
}  // namespace mxnet
