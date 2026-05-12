#!/bin/bash
cd /Users/gengyang/Desktop/AI/Vir
echo "START: $(date)" > /tmp/virc_boot4.log
./core/build/vir run stdlib/vir/compiler/virc.vri -- virc_flat.vri >> /tmp/virc_boot4.log 2>&1
echo "EXIT=$?" >> /tmp/virc_boot4.log
echo "END: $(date)" >> /tmp/virc_boot4.log
