---
date: 2026-07-09
type: fix
status: resolved
---

# Hugo 이미지 처리 시 파일명 255자 초과 오류 (appliance-hugo)

## What
appliance-hugo Hugo 빌드 실패. 오류: `Failed to publish Resource: ... file name too long`
쿠팡 파트너스 이미지 URL(500자↑ base64 인코딩)이 `{{< figure >}}` shortcode로 변환되면서
Hugo가 원격 이미지를 다운로드/처리할 때 생성된 캐시 파일명이 OS 제한(255자) 초과.

## Why
`_apply_figure_shortcode()`가 모든 이미지를 `{{< figure >}}` shortcode로 변환.
Hugo의 Blowfish 테마가 `{{< figure >}}` shortcode에서 이미지를 원격 fetch 후 리사이즈 처리.
이때 생성되는 리소스 파일명에 원본 URL 해시가 포함되는데,
500자 이상의 URL에서 생성된 해시+파일명이 255자 초과.

## Files changed
- `shared/publishers/hugo_writer.py`

## How
`_apply_figure_shortcode()`에서 URL 길이가 300자 초과인 이미지는
`{{< figure >}}` shortcode 대신 일반 마크다운 `![alt](url)` 유지:
```python
if len(url) > 300:
    result.append(f"![{alt}]({url})")  # 일반 이미지
else:
    result.append(f"{{{{< figure src=\"{url}\" ... >}}}}")  # shortcode
```

## Verification
코드 리뷰 완료. Hugo가 해당 이미지를 remote fetch/resize하지 않으므로
파일명 초과 오류가 발생하지 않음.
