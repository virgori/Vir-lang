#!/bin/bash
cd /Users/gengyang/Desktop/AI/Vir
./core/build/vir run stdlib/vir/compiler/virc.vri -- virc_slim.vri > /tmp/virc_boot3.log 2>&1
echo "EXIT=$?" >> /tmp/virc_boot3.log
