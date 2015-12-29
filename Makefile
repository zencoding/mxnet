ifndef config
ifdef CXXNET_CONFIG
	config = $(CXXNET_CONFIG)
else ifneq ("$(wildcard ./config.mk)","")
	config = config.mk
else
	config = make/config.mk
endif
endif

ifndef DMLC_CORE
	DMLC_CORE = dmlc-core
endif

ifneq ($(USE_OPENMP), 1)
	export NO_OPENMP = 1
endif

# use customized config file
include $(config)
include mshadow/make/mshadow.mk
include $(DMLC_CORE)/make/dmlc.mk
unexport NO_OPENMP

# all tge possible warning tread
WARNFLAGS= -Wall
CFLAGS = -DMSHADOW_FORCE_STREAM $(WARNFLAGS)

# CFLAGS for debug
ifeq ($(DEBUG), 1)
	CFLAGS += -g -O0 -DDMLC_LOG_FATAL_THROW=0
else
	CFLAGS += -O3
endif
CFLAGS += -I./mshadow/ -I./dmlc-core/include -fPIC -Iinclude $(MSHADOW_CFLAGS)
LDFLAGS = -pthread $(MSHADOW_LDFLAGS) $(DMLC_LDFLAGS)
ifeq ($(DEBUG), 1)
	NVCCFLAGS = -g -G -O0 -ccbin $(CXX) $(MSHADOW_NVCCFLAGS)
else
	NVCCFLAGS = --use_fast_math -g -O3 -ccbin $(CXX) $(MSHADOW_NVCCFLAGS)
endif
ROOTDIR = $(CURDIR)

ifndef LINT_LANG
	LINT_LANG="all"
endif

# setup opencv
ifeq ($(USE_OPENCV), 1)
	CFLAGS += -DMXNET_USE_OPENCV=1 `pkg-config --cflags opencv`
	LDFLAGS += `pkg-config --libs opencv`
	BIN += bin/im2rec
else
	CFLAGS+= -DMXNET_USE_OPENCV=0
endif

ifeq ($(USE_OPENMP), 1)
	CFLAGS += -fopenmp
endif

ifeq ($(USE_CUDNN), 1)
	CFLAGS += -DMSHADOW_USE_CUDNN=1
	LDFLAGS += -lcudnn
endif

ifeq ($(USE_THREADED_ENGINE), 1)
	CFLAGS += -DMXNET_USE_THREADED_ENGINE
endif

ifneq ($(ADD_CFLAGS), NONE)
	CFLAGS += $(ADD_CFLAGS)
endif

ifneq ($(ADD_LDFLAGS), NONE)
	LDFLAGS += $(ADD_LDFLAGS)
endif

ifneq ($(USE_CUDA_PATH), NONE)
	NVCC=$(USE_CUDA_PATH)/bin/nvcc
endif

# ps-lite
PS_PATH=./ps-lite
DEPS_PATH=$(shell pwd)/deps
include $(PS_PATH)/make/ps.mk
ifeq ($(USE_DIST_KVSTORE), 1)
	CFLAGS += -DMXNET_USE_DIST_KVSTORE -I$(PS_PATH)/include -I$(DEPS_PATH)/include
	LIB_DEP += $(PS_PATH)/build/libps.a
	LDFLAGS += $(PS_LDFLAGS_A)
endif

.PHONY: clean all test lint doc clean_all rcpplint rcppexport roxygen

all: lib/libmxnet.a lib/libmxnet.so $(BIN)

SRC = $(wildcard src/*.cc src/*/*.cc)
OBJ = $(patsubst src/%.cc, build/%.o, $(SRC))
CUSRC = $(wildcard src/*/*.cu)
CUOBJ = $(patsubst src/%.cu, build/%_gpu.o, $(CUSRC))

ifneq ($(EXTRA_OPERATORS),)
	EXTRA_SRC = $(wildcard $(EXTRA_OPERATORS)/*.cc $(EXTRA_OPERATORS)/*/*.cc)
	EXTRA_OBJ = $(patsubst $(EXTRA_OPERATORS)/%.cc, $(EXTRA_OPERATORS)/build/%.o, $(EXTRA_SRC))
	EXTRA_CUSRC = $(wildcard $(EXTRA_OPERATORS)/*.cu $(EXTRA_OPERATORS)/*/*.cu)
	EXTRA_CUOBJ = $(patsubst $(EXTRA_OPERATORS)/%.cu, $(EXTRA_OPERATORS)/build/%_gpu.o, $(EXTRA_CUSRC))
else
	EXTRA_SRC =
	EXTRA_OBJ =
	EXTRA_CUSRC =
	EXTRA_CUOBJ =
endif

LIB_DEP += $(DMLC_CORE)/libdmlc.a
ALL_DEP = $(OBJ) $(EXTRA_OBJ) $(LIB_DEP)
ifeq ($(USE_CUDA), 1)
	ALL_DEP += $(CUOBJ) $(EXTRA_CUOBJ)
	LDFLAGS += -lcuda
endif

ifeq ($(USE_NVRTC), 1)
	LDFLAGS += -lnvrtc
	CFLAGS += -DMXNET_USE_NVRTC=1
else
	CFLAGS += -DMXNET_USE_NVRTC=0
endif


build/%.o: src/%.cc
	@mkdir -p $(@D)
	$(CXX) -std=c++0x $(CFLAGS) -MM -MT build/$*.o $< >build/$*.d
	$(CXX) -std=c++0x -c $(CFLAGS) -c $< -o $@

build/%_gpu.o: src/%.cu
	@mkdir -p $(@D)
	$(NVCC) $(NVCCFLAGS) -Xcompiler "$(CFLAGS)" -M -MT build/$*_gpu.o $< >build/$*_gpu.d
	$(NVCC) -c -o $@ $(NVCCFLAGS) -Xcompiler "$(CFLAGS)" $<

$(EXTRA_OPERATORS)/build/%.o: $(EXTRA_OPERATORS)/%.cc
	@mkdir -p $(@D)
	$(CXX) -std=c++0x $(CFLAGS) -Isrc/operator -MM -MT $(EXTRA_OPERATORS)/build/$*.o $< >$(EXTRA_OPERATORS)/build/$*.d
	$(CXX) -std=c++0x -c $(CFLAGS) -Isrc/operator -c $< -o $@

$(EXTRA_OPERATORS)/build/%_gpu.o: $(EXTRA_OPERATORS)/%.cu
	@mkdir -p $(@D)
	$(NVCC) $(NVCCFLAGS) -Xcompiler "$(CFLAGS) -Isrc/operator" -M -MT $(EXTRA_OPERATORS)/build/$*_gpu.o $< >$(EXTRA_OPERATORS)/build/$*_gpu.d
	$(NVCC) -c -o $@ $(NVCCFLAGS) -Xcompiler "$(CFLAGS) -Isrc/operator" $<

lib/libmxnet.a: $(ALL_DEP)
	@mkdir -p $(@D)
	ar crv $@ $(filter %.o, $?)

lib/libmxnet.so: $(ALL_DEP)
	@mkdir -p $(@D)
	$(CXX) $(CFLAGS) -shared -o $@ $(filter %.o %.a, $^) $(LDFLAGS)

# ps-lite
$(PS_PATH)/build/libps.a:
	$(MAKE) CXX=$(CXX) DEPS_PATH=$(DEPS_PATH) -C $(PS_PATH) ps
	ln -fs $(PS_PATH)/tracker .

$(DMLC_CORE)/libdmlc.a:
	+ cd $(DMLC_CORE); make libdmlc.a config=$(ROOTDIR)/$(config); cd $(ROOTDIR)

bin/im2rec: tools/im2rec.cc $(ALL_DEP)

$(BIN) :
	@mkdir -p $(@D)
	$(CXX) $(CFLAGS)  -o $@ $(filter %.cpp %.o %.c %.a %.cc, $^) $(LDFLAGS)

include tests/cpp/unittest.mk

test: $(TEST)

lint: rcpplint
	python2 dmlc-core/scripts/lint.py mxnet ${LINT_LANG} include src scripts python predict/python

doc: doxygen

doxygen:
	doxygen doc/Doxyfile

# R related shortcuts
rcpplint:
	python2 dmlc-core/scripts/lint.py mxnet-rcpp ${LINT_LANG} R-package/src

rcppexport:
	Rscript -e "require(mxnet); mxnet::mxnet.export(\"R-package\")"

roxygen:
	Rscript -e "require(roxygen2); roxygen2::roxygenise(\"R-package\")"

rpkg:	roxygen
	mkdir -p R-package/inst
	mkdir -p R-package/inst/libs
	cp -rf lib/libmxnet.so R-package/inst/libs
	mkdir -p R-package/inst/include
	cp -rf include/* R-package/inst/include
	cp -rf dmlc-core/include/* R-package/inst/include/
	R CMD build --no-build-vignettes R-package

clean:
	$(RM) -r build lib bin *~ */*~ */*/*~ */*/*/*~

clean_all: clean
	cd $(DMLC_CORE); make clean; cd -
	cd $(PS_PATH); make clean; cd -

-include build/*.d
-include build/*/*.d
ifneq ($(EXTRA_OPERATORS),)
	-include $(EXTRA_OPERATORS)/build/*.d
endif
