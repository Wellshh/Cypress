/**
 * File              : utils_cub.cuh
 * Author            : Yibo Lin <yibolin@pku.edu.cn>
 * Date              : 06.25.2021
 * Last Modified Date: 06.25.2021
 * Last Modified By  : Yibo Lin <yibolin@pku.edu.cn>
 */

#ifndef _DREAMPLACE_UTILITY_UTILS_CUB_CUH
#define _DREAMPLACE_UTILITY_UTILS_CUB_CUH

#include "utility/src/namespace.h"

// include cub directly; namespace wrapping removed for CUDA 12+ compatibility
#include "cub/cub.cuh"

// create namespace alias so existing cub:: references inside DREAMPLACE_NAMESPACE work
DREAMPLACE_BEGIN_NAMESPACE
namespace cub = ::cub;
DREAMPLACE_END_NAMESPACE

#endif
