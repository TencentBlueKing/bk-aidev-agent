#!/bin/bash
# DO NOT MODIFY THIS SECTION !!!
total_start=$(date +%s%3N)

echo "[Migrate] BEGIN ===================="
migrate_start=$(date +%s%3N)
python bin/manage.py migrate --no-input
migrate_end=$(date +%s%3N)
migrate_ms=$((migrate_end - migrate_start))
echo "[Migrate] DONE ====================="


echo "[Cachetable] BEGIN ================="
cachetable_start=$(date +%s%3N)
python bin/manage.py createcachetable
cachetable_end=$(date +%s%3N)
cachetable_ms=$((cachetable_end - cachetable_start))
echo "[Cachetable] DONE =================="


echo "[Sync] BEGIN ===================c====="
sync_start=$(date +%s%3N)
python bin/manage.py sync_apigateway_if_changed
if [ $? -ne 0 ]
then
    echo "sync_apigateway_if_changed fail"
    exit 1
fi
sync_end=$(date +%s%3N)
sync_ms=$((sync_end - sync_start))
echo "[Sync] DONE ========================="

total_end=$(date +%s%3N)
total_ms=$((total_end - total_start))

echo ""
echo "=============== 耗时统计 ==============="
echo "Migrate:      $((migrate_ms / 1000)).$((migrate_ms % 1000))s"
echo "Cachetable:   $((cachetable_ms / 1000)).$((cachetable_ms % 1000))s"
echo "Sync:         $((sync_ms / 1000)).$((sync_ms % 1000))s"
echo "----------------------------------------"
echo "总耗时:        $((total_ms / 1000)).$((total_ms % 1000))s"
echo "========================================"
# DO NOT MODIFY THIS SECTION !!!