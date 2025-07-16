# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AI Blueking (AI小鲸) is a reusable Vue.js component library providing AI chatbot functionality. It's designed as a cross-framework component supporting both Vue 2 and Vue 3, intended for integration into Blueking PaaS applications.

## Project Structure

```
src/
├── ai-blueking-new.vue      # Main draggable chat component
├── vue3.ts                  # Vue 3 entry point
├── vue2.ts                  # Vue 2 entry point (wrapper)
├── components/              # UI components (chat-input-box, render-message, etc.)
├── composables/             # Vue 3 Composition API utilities
├── config/                  # Configuration files
├── types/                   # TypeScript definitions
├── utils/                   # Utility functions
├── styles/                  # SCSS styles and mixins
├── plugins/                 # Vue plugins
└── lang/                    # Internationalization
```

## Environment Setup

This project uses **Node.js v20** and **pnpm** for package management. Always run these commands before any development work:

```bash
nvm use v20    # Switch to Node.js v20
pnpm install   # Install dependencies
```

## Development Commands

```bash
# Development
pnpm run dev                 # Start dev server (port 8001)

# Build
pnpm run build              # Build for production (multi-format)
pnpm run dts                # Generate TypeScript declarations

# Code Quality
pnpm run lint               # Run ESLint
pnpm run lint:fix          # Auto-fix lint issues
pnpm run prettier          # Format code
pnpm run visualize         # Bundle analyzer

# Clean
pnpm run clean             # Remove dist and node_modules
```

## Architecture Notes

- **Dual Framework Support**: Separate builds for Vue 2 and Vue 3 via `vue2.ts` and `vue3.ts`
- **Library Mode**: Built as NPM package, not a standalone app
- **Entry Points**:
  - Vue 3: `dist/vue3/index.es.min.js`
  - Vue 2: `dist/vue2/index.es.min.js`
- **Styling**: SCSS with CSS custom properties, BEM-like naming with `bk-` prefix
- **Dependencies**: Uses @blueking/ai-ui-sdk, motion-v for animations, vue-draggable-resizable

## Key Patterns

- **Composition API**: Heavy use of Vue 3 composables in `composables/`
- **Type Safety**: Full TypeScript with strict configuration
- **Event-driven**: Uses Vue event system for communication
- **Cross-framework**: Vue 2 compatibility via wrapper component
- **I18n**: Built-in internationalization with Chinese as primary language

## Integration

- **Library Usage**: `import AiBlueking from '@blueking/ai-blueking'`
- **Vue 2**: `import AiBlueking from '@blueking/ai-blueking/vue2'`
- **CDN**: Available via unpkg as IIFE build
- **Props-based**: Configurable via component props
- **Events**: Emits events for user interactions
