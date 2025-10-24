TARGET_MODEL ?= bmv2

all: copysrc
	@echo "Generating SAI for target: $(TARGET_MODEL)"

	@{ \
		if [ "$(TARGET_MODEL)" = "bmv2" ]; then \
			ARTIFACTS_DIR="../bmv2/dash_pipeline.bmv2"; \
		elif [ "$(TARGET_MODEL)" = "pymodel" ]; then \
			ARTIFACTS_DIR="../py_model/dash_pipeline.py_model"; \
		else \
			echo "Error: Unknown TARGET_MODEL='$(TARGET_MODEL)'. Use 'bmv2' or 'pymodel'."; \
			exit 1; \
		fi; \
		echo "Using artifacts from: $$ARTIFACTS_DIR"; \
		if [ ! -f "$$ARTIFACTS_DIR/dash_pipeline_p4rt.json" ]; then \
			echo "Error: $$ARTIFACTS_DIR/dash_pipeline_p4rt.json not found."; \
			exit 1; \
		fi; \
		./sai_api_gen.py \
			$$ARTIFACTS_DIR/dash_pipeline_p4rt.json \
			--ir $$ARTIFACTS_DIR/dash_pipeline_ir.json \
			--ignore-tables=underlay_mac,eni_meter,slb_decap \
			--sai-spec-dir=specs \
			dash; \
	}

copysrc:
	install -CDv src/Makefile src/*h src/*cpp lib/
.PHONY: clean
clean:
	rm -f lib/*
