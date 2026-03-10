#!/bin/bash

# Author André Kapelrud, Robert Marskar
# Copyright © 2026 SINTEF Energi AS

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

for i in run_*/; do
	cd $i
	echo "parameters.json:"
	cat parameters.json
	echo ""
	python "$SCRIPT_DIR/Gather.py"
	echo -e "\n===================================\n"
	cd ..
done
