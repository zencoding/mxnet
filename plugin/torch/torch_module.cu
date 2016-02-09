/*!
 * Copyright (c) 2015 by Contributors
 * \file activation.cc
 * \brief activation op
 * \author Bing Xu
*/
#include "./torch_module-inl.h"
#include "../../src/operator/mshadow_op.h"

namespace mxnet {
namespace op {
template<>
Operator *CreateOp<gpu>(TorchModuleParam param) {
  return new TorchModuleOp<gpu>(param);
}

}  // namespace op
}  // namespace mxnet
