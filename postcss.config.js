const purgecss = require('@fullhuman/postcss-purgecss')({
  content: [
    './layouts/**/*.html',
    './content/**/*.md',
    './themes/PaperMod/layouts/**/*.html'
  ],
  defaultExtractor: content => content.match(/[\w-/:]+(?<!:)/g) || [],
  safelist: {
    standard: [
      /^html/,
      /^body/,
      /^main/,
      /^header/,
      /^footer/,
      /^nav/,
      /^article/,
      /data-theme/,
      /dark/,
      /light/,
      /active/,
      /focus/,
      /hover/,
      /show/,
      /hide/,
      /open/,
      /closed/,
      /^ad-/,
      /^adsbygoogle/,
      /^ins/,
      /^chroma/,
      /^highlight/,
      /^language-/,
      /^post-/,
      /^entry-/,
      /^archive-/,
      /^pagination/,
      /^toc/,
      /^search/,
      /^social/,
      /^share/,
      /^btn/,
      /^top-link/,
      /^logo/,
      /^menu/,
      /^breadcrumbs/,
      /^related/
    ],
    deep: [
      /data-theme$/
    ],
    greedy: [
      /adsbygoogle/,
      /chroma/
    ]
  }
});

module.exports = {
  plugins: [
    require('autoprefixer'),
    ...(process.env.HUGO_ENVIRONMENT === 'production' ? [purgecss] : [])
  ]
}
