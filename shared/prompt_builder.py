import os
import re

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "writing_samples")


def load_prompts():
    """config/prompts/*.yaml을 모두 합쳐 반환. 없으면 단일 파일 폴백."""
    prompts_dir = os.path.join(CONFIG_DIR, "prompts")
    if os.path.isdir(prompts_dir):
        merged = {}
        for fname in sorted(os.listdir(prompts_dir)):
            if fname.endswith(".yaml"):
                with open(os.path.join(prompts_dir, fname), encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data:
                    merged.update(data)
        return merged
    # 폴백: 기존 단일 파일
    with open(os.path.join(CONFIG_DIR, "prompts.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _strip_frontmatter(text: str) -> str:
    """마크다운 앞부분 frontmatter(--- ... ---) 제거 후 본문만 반환."""
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    return text[end + 3:]


def _extract_sample_sections(sample_text: str, max_chars: int = 2500) -> str:
    """샘플 글에서 도입부 + 첫 H2 + 마무리만 발췌. 총 길이가 max_chars 이하가 되도록."""
    body = _strip_frontmatter(sample_text).strip()
    # 본문에서 도입부(처음 ~ 첫 H2 전까지), H2 섹션 1개, 마지막 문단(발췌)
    lines = body.split("\n")
    # 1) 도입부: 첫 H2 전까지
    intro_lines = []
    h2_idx = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            h2_idx = i
            break
        if line.strip():
            intro_lines.append(line)
    # 2) H2 섹션 하나: 첫 H2부터 다음 H2 전까지
    section_lines = []
    if h2_idx is not None:
        section_start = h2_idx
        section_end = None
        for i in range(h2_idx + 1, len(lines)):
            if lines[i].startswith("## "):
                section_end = i
                break
        if section_end is None:
            section_end = len(lines)
        section_lines = lines[section_start:section_end]
    # 3) 마무리 문단: 마지막 H2 섹션의 본문 중 마지막 3문단
    closing_lines = []
    if h2_idx is not None and section_end is not None:
        closing_block = lines[section_end:]
        # 마지막 빈 줄 아닌 문단 3개 추출
        paragraphs = []
        cur = []
        for line in closing_block:
            if line.strip() == "":
                if cur:
                    paragraphs.append(cur)
                    cur = []
            else:
                cur.append(line)
        if cur:
            paragraphs.append(cur)
        closing_lines = [ln for p in paragraphs[-3:] for ln in p]

    selected = intro_lines + [""] + section_lines + [""] + closing_lines
    result = "\n".join(selected).strip()
    if len(result) > max_chars:
        result = result[:max_chars].rsplit("\n", 1)[0] + "\n..."
    return result


def load_samples(category: str | None = None, limit: int = 3) -> list[str]:
    """writing_samples 디렉터리에서 샘플 마크다운 파일을 읽어 본문 발췌 목록 반환.

    category: None이면 전체, 지정된 파일이름 키워드가 있으면 부분 집합만.
    limit: 최대 로딩 개수. 샘플이 부족하면 그만큼만 반환.
    """
    if not os.path.isdir(SAMPLES_DIR):
        return []
    files = sorted(os.listdir(SAMPLES_DIR))
    if category:
        files = [f for f in files if category.lower() in f.lower()]
    samples = []
    for fname in files[:limit]:
        if not fname.endswith((".md", ".markdown", ".txt")):
            continue
        fpath = os.path.join(SAMPLES_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                raw = f.read()
            excerpt = _extract_sample_sections(raw)
            if excerpt:
                samples.append(excerpt)
        except OSError:
            continue
    return samples


def build(prompt_id, data, extra_vars=None, inject_samples: bool = False, sample_category: str | None = None):
    """프롬프트 템플릿 + 데이터 + (선택) 글쓰기 샘플 주입.

    inject_samples=True이면 writing_samples 디렉터리에서 샘플 본문을 읽어
    user 프롬프트 끝에 예시 참고로 추가한다. sample_category로 필터링 가능.
    """
    prompts = load_prompts()
    if prompt_id not in prompts:
        raise ValueError("Unknown prompt_id: " + prompt_id)

    template = prompts[prompt_id]
    system_prompt = template["system"].strip()
    user_prompt = template["user"].strip()

    user_prompt = user_prompt.replace("{data}", data)

    # 글쓰기 샘플 주입
    if inject_samples:
        samples = load_samples(category=sample_category, limit=2)
        if samples:
            samples_text = "## 참고 글 예시 (글쓰기 기준)\n\n아래 글은 같은 계열에서 잘 쓴 글의 표본 예문입니다. 이 예문을 글쓰기의 기준으로 삼아, 톤(~입니다/~습니다), 문단 구성, 정보 전달 방식, 표와 체크리스트 활용 방식을 그대로 따르십시오. 내용만 새 데이터로 작성하고, 글쓰기 방식은 예문을 따릅니다.\n\n"
            for i, s in enumerate(samples, 1):
                samples_text += f"### 예시 글 {i}\n\n{s}\n\n"
            user_prompt = user_prompt + "\n\n" + samples_text

    if extra_vars:
        for key, value in extra_vars.items():
            user_prompt = user_prompt.replace("{" + key + "}", str(value))

    return {
        "system": system_prompt,
        "user": user_prompt,
        "prompt_id": prompt_id,
    }
