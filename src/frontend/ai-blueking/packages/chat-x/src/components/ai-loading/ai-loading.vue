<template>
  <div
    class="ai-loading"
    :class="{ 'ai-loading-stopped': stopLoading }"
    :style="{ width: size + 'px', height: size + 'px' }"
  >
    <div class="ai-loading-ring">
      <svg
        fill="none"
        viewBox="0 0 26 26"
      >
        <path
          d="M24.957 7.79785C25.6279 9.36608 26 11.0926 26 12.9062C26 19.5598 21.0013 25.0441 14.5547 25.8125L14.3154 23.8252C19.7702 23.175 24 18.5361 24 12.9062C24 11.3717 23.6848 9.91092 23.1172 8.58398L24.957 7.79785ZM11.6836 1.98633C6.2292 2.63694 2 7.27669 2 12.9062C2 14.4404 2.31452 15.9009 2.88184 17.2275L1.04199 18.0137C0.371448 16.4458 0 14.7194 0 12.9062C0 6.25306 4.99814 0.768818 11.4443 0L11.6836 1.98633Z"
          :fill="`url(#${ringGradientId})`"
        />
        <defs>
          <linearGradient
            :id="ringGradientId"
            gradientUnits="userSpaceOnUse"
            x1="6.50423"
            x2="25.6886"
            y1="2.96507"
            y2="19.2824"
          >
            <stop stop-color="#235DFA" />
            <stop
              offset="0.538462"
              stop-color="#8A77EC"
            />
            <stop
              offset="1"
              stop-color="#EB8CEC"
            />
          </linearGradient>
        </defs>
      </svg>
    </div>
    <div class="ai-loading-star">
      <svg
        fill="none"
        viewBox="0 0 26 26"
      >
        <path
          d="M13 5.90625C13 5.90625 14.1206 8.77684 15.625 10.2812C17.1294 11.7857 20 12.9062 20 12.9062C20 12.9062 17.1294 14.0268 15.625 15.5312C14.1206 17.0357 13 19.9062 13 19.9062C13 19.9062 11.8794 17.0357 10.375 15.5312C8.87059 14.0268 6 12.9062 6 12.9062C6 12.9062 8.87059 11.7857 10.375 10.2812C11.8794 8.77684 13 5.90625 13 5.90625Z"
          :fill="`url(#${starGradientId})`"
        />
        <defs>
          <linearGradient
            :id="starGradientId"
            gradientUnits="userSpaceOnUse"
            x1="6"
            x2="20"
            y1="5.90625"
            y2="19.9062"
          >
            <stop stop-color="#235DFA" />
            <stop
              offset="0.538462"
              stop-color="#8A77EC"
            />
            <stop
              offset="1"
              stop-color="#EB8CEC"
            />
          </linearGradient>
        </defs>
      </svg>
    </div>
  </div>
</template>
<script setup lang="ts">
  defineOptions({ name: 'AiLoading' });

  let uid = 0;

  withDefaults(
    defineProps<{
      size?: number;
      stopLoading?: boolean;
    }>(),
    {
      size: 16,
      stopLoading: false,
    },
  );

  const instanceId = uid++;
  const ringGradientId = `ai-loading-ring-${instanceId}`;
  const starGradientId = `ai-loading-star-${instanceId}`;
</script>
<style lang="scss">
  .ai-loading {
    position: relative;
    display: inline-flex;
    width: 1em;
    height: 1em;
    font-size: 1em;

    &-ring,
    &-star {
      position: absolute;

      svg {
        display: block;
        width: 100%;
        height: 100%;
      }
    }

    &-ring {
      animation: ai-loading-rotate 0.8s linear infinite;
    }

    &-star {
      animation: ai-loading-pulse 0.8s ease-in-out infinite;
    }

    &-stopped &-ring,
    &-stopped &-star {
      animation-play-state: paused;
    }
  }

  @keyframes ai-loading-rotate {
    from {
      transform: rotate(0deg);
    }

    to {
      transform: rotate(360deg);
    }
  }

  @keyframes ai-loading-pulse {
    0%,
    100% {
      transform: scale(0.5);
    }

    50% {
      transform: scale(1);
    }
  }
</style>
