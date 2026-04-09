<template>
  <div class="custom-content">
    <div class="custom-content-content">
      <div
        ref="treeMapRef"
        class="tree-map-chart"
      ></div>
      <div>
        <Button
          theme="primary"
          @click="handleClick"
        >
          查看详情
        </Button>
      </div>
    </div>
    <template v-if="detailVisible && messageSlotId">
      <Teleport :to="messageSlotId">
        <div class="custom-content-slot">
          <div
            id="stock-chart"
            ref="stockChartRef"
          ></div>
          <Button
            theme="primary"
            @click="handleClick"
          >
            关闭
          </Button>
        </div>
      </Teleport>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { nextTick, onMounted, shallowRef, useTemplateRef, watch } from 'vue';

  import { Button } from 'bkui-vue';
  import * as echarts from 'echarts';

  import { type BaseMessage, useMessageSlotId } from '../../src';
  import { stockData, treeMapData } from './stock';
  import { calculateMA, splitData } from './stock-echarts';
  import { generateTreeMap } from './tree-map';
  const treeMapRef = useTemplateRef<HTMLElement>('treeMapRef');
  const data = splitData(stockData as number[][]);
  const upColor = '#00da3c';
  const downColor = '#ec0000';
  defineProps<{
    message: Partial<
      BaseMessage<
        'custom',
        {
          content: string;
          id: string;
          name: string;
          slot?: string;
        }
      >
    >;
  }>();
  const { messageSlotId } = useMessageSlotId();
  const detailVisible = shallowRef(false);
  const handleClick = () => {
    detailVisible.value = !detailVisible.value;
  };

  const myChart = shallowRef<echarts.ECharts | null>(null);

  watch(detailVisible, async () => {
    if (detailVisible.value) {
      await nextTick();
      if (myChart.value) {
        myChart.value.clear();
        myChart.value.dispose();
      }
      await nextTick();
      myChart.value = echarts.init(document.getElementById('stock-chart') as HTMLElement);
      myChart.value.setOption(
        {
          animation: false,
          legend: {
            bottom: 10,
            left: 'center',
            data: ['Dow-Jones index', 'MA5', 'MA10', 'MA20', 'MA30'],
          },
          tooltip: {
            trigger: 'axis',
            axisPointer: {
              type: 'cross',
            },
            borderWidth: 1,
            borderColor: '#ccc',
            padding: 10,
            textStyle: {
              color: '#000',
            },
            position: function (
              pos: number[],
              _params: unknown,
              _el: unknown,
              _elRect: unknown,
              size: { viewSize: [number, number] },
            ) {
              const obj: Record<string, number> = {
                top: 10,
              };
              obj[['left', 'right'][+(pos[0]! < size.viewSize[0]! / 2)]!] = 30;
              return obj;
            },
            // extraCssText: 'width: 170px'
          },
          axisPointer: {
            link: [
              {
                xAxisIndex: 'all',
              },
            ],
            label: {
              backgroundColor: '#777',
            },
          },
          toolbox: {
            feature: {
              dataZoom: {
                yAxisIndex: false,
              },
              brush: {
                type: ['lineX', 'clear'],
              },
            },
          },
          brush: {
            xAxisIndex: 'all',
            brushLink: 'all',
            outOfBrush: {
              colorAlpha: 0.1,
            },
          },
          visualMap: {
            show: false,
            seriesIndex: 5,
            dimension: 2,
            pieces: [
              {
                value: 1,
                color: downColor,
              },
              {
                value: -1,
                color: upColor,
              },
            ],
          },
          grid: [
            {
              left: '10%',
              right: '8%',
              height: '50%',
            },
            {
              left: '10%',
              right: '8%',
              top: '63%',
              height: '16%',
            },
          ],
          xAxis: [
            {
              type: 'category',
              data: data.categoryData,
              boundaryGap: false,
              axisLine: { onZero: false },
              splitLine: { show: false },
              min: 'dataMin',
              max: 'dataMax',
              axisPointer: {
                z: 100,
              },
            },
            {
              type: 'category',
              gridIndex: 1,
              data: data.categoryData,
              boundaryGap: false,
              axisLine: { onZero: false },
              axisTick: { show: false },
              splitLine: { show: false },
              axisLabel: { show: false },
              min: 'dataMin',
              max: 'dataMax',
            },
          ],
          yAxis: [
            {
              scale: true,
              splitArea: {
                show: true,
              },
            },
            {
              scale: true,
              gridIndex: 1,
              splitNumber: 2,
              axisLabel: { show: false },
              axisLine: { show: false },
              axisTick: { show: false },
              splitLine: { show: false },
            },
          ],
          dataZoom: [
            {
              type: 'inside',
              xAxisIndex: [0, 1],
              start: 98,
              end: 100,
            },
            {
              show: true,
              xAxisIndex: [0, 1],
              type: 'slider',
              top: '85%',
              start: 98,
              end: 100,
            },
          ],
          series: [
            {
              name: 'Dow-Jones index',
              type: 'candlestick',
              data: data.values,
              itemStyle: {
                color: upColor,
                color0: downColor,
                borderColor: undefined,
                borderColor0: undefined,
              },
            },
            {
              name: 'MA5',
              type: 'line',
              data: calculateMA(5, data as { values: number[][] }),
              smooth: true,
              lineStyle: {
                opacity: 0.5,
              },
            },
            {
              name: 'MA10',
              type: 'line',
              data: calculateMA(10, data as { values: number[][] }),
              smooth: true,
              lineStyle: {
                opacity: 0.5,
              },
            },
            {
              name: 'MA20',
              type: 'line',
              data: calculateMA(20, data as { values: number[][] }),
              smooth: true,
              lineStyle: {
                opacity: 0.5,
              },
            },
            {
              name: 'MA30',
              type: 'line',
              data: calculateMA(30, data as { values: number[][] }),
              smooth: true,
              lineStyle: {
                opacity: 0.5,
              },
            },
            {
              name: 'Volume',
              type: 'bar',
              xAxisIndex: 1,
              yAxisIndex: 1,
              data: data.volumes,
            },
          ],
        },
        true,
      );

      myChart.value.dispatchAction({
        type: 'brush',
        areas: [
          {
            brushType: 'lineX',
            coordRange: ['2016-06-02', '2016-06-20'],
            xAxisIndex: 0,
          },
        ],
      });
    }
  });
  onMounted(() => {
    const treeMapChart = echarts.init(treeMapRef.value);
    const { treemapOption, sunburstOption } = generateTreeMap(treeMapData);
    let currentOption = treemapOption;
    setInterval(function () {
      currentOption = currentOption === treemapOption ? sunburstOption : treemapOption;
      treeMapChart.setOption(currentOption);
    }, 3000);
    setTimeout(() => {
      detailVisible.value = true;
    }, 3000);
  });
</script>
<style lang="scss">
  .custom-content {
    display: flex;

    &-content {
      display: flex;
      align-items: center;
      width: 100%;

      // height: 100px;
      padding: 16px;
      font-size: 16px;
      background-color: #f0f0f0;
    }
  }

  .tree-map-chart,
  #stock-chart {
    width: 680px;
    height: 500px;
  }
</style>
