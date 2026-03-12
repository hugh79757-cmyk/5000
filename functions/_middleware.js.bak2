export async function onRequest(context) {
  const url = new URL(context.request.url);
  const path = url.pathname;
  let needsRedirect = false;
  let targetPath = path;
  let targetSearch = url.search;

  // 1. /m/ 제거
  if (targetPath.startsWith('/m/')) {
    targetPath = targetPath.replace(/^\/m/, '');
    needsRedirect = true;
  }

  // 2. /comments 제거
  if (targetPath.endsWith('/comments') || targetPath.endsWith('/comments/')) {
    targetPath = targetPath.replace(/\/comments\/?$/, '/');
    needsRedirect = true;
  }

  // 3. /entry/xxx -> /posts/xxx/
  if (targetPath.startsWith('/entry/')) {
    const slug = targetPath.replace(/^\/entry\//, '').replace(/\/$/, '');
    targetPath = slug ? '/posts/' + slug + '/' : '/';
    needsRedirect = true;
  }

  // 4. 숫자 ID -> 홈
  if (/^\/\d+\/?$/.test(targetPath)) {
    targetPath = '/';
    needsRedirect = true;
  }

  // 5. /tag/ -> /tags/
  if (targetPath.startsWith('/tag/')) {
    targetPath = '/tags/';
    needsRedirect = true;
  }

  // 6. /category -> /categories/
  if (targetPath.startsWith('/category')) {
    targetPath = '/categories/';
    needsRedirect = true;
  }

  // 7. /guestbook -> 홈
  if (targetPath === '/guestbook' || targetPath === '/guestbook/') {
    targetPath = '/';
    needsRedirect = true;
  }

  // 8. /file/ -> 홈
  if (targetPath.startsWith('/file/')) {
    targetPath = '/';
    needsRedirect = true;
  }

  // 9. /posts/날짜-제목 -> /posts/제목
  const dateMatch = targetPath.match(/^\/posts\/\d{4}-\d{2}-\d{2}-(.+)$/);
  if (dateMatch) {
    targetPath = '/posts/' + dateMatch[1];
    needsRedirect = true;
  }

  // 10. 쿼리 파라미터 정리 (category, page, ref_src)
  if (url.searchParams.has('category') || url.searchParams.has('page') || url.searchParams.has('ref_src')) {
    targetSearch = '';
    needsRedirect = true;
  }

  // 11. 경로에 인코딩된 category 파라미터
  if (targetPath.includes('category%3D') || targetPath.includes('category=')) {
    targetPath = targetPath.split('?')[0].replace(/[?&]?category(%3D|=)[^/&]*/gi, '');
    targetSearch = '';
    needsRedirect = true;
  }

  if (needsRedirect) {
    const finalUrl = url.origin + targetPath + (targetSearch || '');
    return Response.redirect(finalUrl, 301);
  }

  return context.next();
}
