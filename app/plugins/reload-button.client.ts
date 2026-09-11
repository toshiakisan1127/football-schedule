export default defineNuxtPlugin(() => {
  const buttonId = 'pwa-reload-button'
  const styleId = 'pwa-reload-button-style'

  if (document.getElementById(buttonId)) return

  const button = document.createElement('button')
  button.id = buttonId
  button.type = 'button'
  button.className = 'pwa-reload-button'
  button.textContent = '↻'
  button.setAttribute('aria-label', 'ページを再読み込み')
  button.title = '再読み込み'
  button.addEventListener('click', () => window.location.reload())

  if (!document.getElementById(styleId)) {
    const style = document.createElement('style')
    style.id = styleId
    style.textContent = `
      .pwa-reload-button {
        position: fixed;
        right: max(16px, env(safe-area-inset-right));
        bottom: max(16px, env(safe-area-inset-bottom));
        z-index: 900;
        display: grid;
        width: 44px;
        height: 44px;
        place-items: center;
        border: 1px solid var(--border-strong);
        border-radius: 50%;
        background: var(--surface);
        color: var(--text);
        box-shadow: 0 8px 24px rgb(0 0 0 / 24%);
        font: inherit;
        font-size: 1.45rem;
        line-height: 1;
        cursor: pointer;
        -webkit-tap-highlight-color: transparent;
      }

      .pwa-reload-button:hover {
        background: var(--surface-muted);
      }

      .pwa-reload-button:focus-visible {
        outline: 2px solid var(--text);
        outline-offset: 2px;
      }

      .pwa-reload-button:active {
        transform: scale(0.96);
      }
    `
    document.head.appendChild(style)
  }

  document.body.appendChild(button)
})
