<template>
  <section class="access-card">
    <div class="access-body">
      <slot />
    </div>
    <div
      v-if="$slots.actions"
      class="access-actions"
    >
      <slot name="actions" />
    </div>
  </section>
</template>

<style lang="postcss" scoped>
  .access-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
    width: 550px;
    max-width: calc(100vw - 48px);
    box-sizing: border-box;
    padding: 24px 32px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(25, 25, 41, 0.05);
  }

  .access-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    width: 100%;
  }

  .access-actions {
    display: flex;
    align-items: center;
    justify-content: center;
  }
</style>
