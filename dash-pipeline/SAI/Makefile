TARGET_TYPE ?= bmv2

all: copysrc
	@if [ "$(TARGET_TYPE)" = "bmv2" ]; then \
		echo "Generating SAI for BMv2 target..."; \
		FILE_PATH="/bmv2/dash_pipeline.bmv2"; \
	elif [ "$(TARGET_TYPE)" = "pymodel" ]; then \
		echo "Generating SAI for PyModel target..."; \
		FILE_PATH="/py_model/dash_pipeline/dash_pipeline.py_model"; \
	else \
		echo "Error: Unknown TARGET_TYPE=$(TARGET_TYPE). Use 'bmv2' or 'pymodel'"; \
		exit 1; \
	fi; \
	./sai_api_gen.py \
		$$FILE_PATH/dash_pipeline_p4rt.json \
		--ir $$FILE_PATH/dash_pipeline_ir.json \
		--ignore-tables=underlay_mac,eni_meter,slb_decap \
		--sai-spec-dir=specs \
		dash

copysrc:
	install -CDv src/Makefile src/*h src/*cpp lib/
.PHONY: clean
clean:
	rm -f lib/*
