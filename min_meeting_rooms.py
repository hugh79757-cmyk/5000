def min_meeting_rooms(meetings: list[tuple[int, int]]) -> int:
    """모든 회의를 진행하기 위해 필요한 최소 회의실 개수.

    시작/종료 시각을 분리해 정렬한 뒤 두 포인터로 스윕한다.
    - 종료 시각은 "같은 시각에 시작"을 허용하므로 시작과 비교할 때
      start >= end 면 먼저 방을 비운다(end 포인터를 먼저 전진).
    - 시간 복잡도: O(n log n), 공간 복잡도: O(n)
    """
    if not meetings:
        return 0

    starts = sorted(s for s, _ in meetings)
    ends = sorted(e for _, e in meetings)

    rooms = 0
    max_rooms = 0
    i = j = 0
    n = len(meetings)

    while i < n:
        if starts[i] >= ends[j]:
            # 기존 방 하나가 비워진다 (종료 시각에 새 회의 시작 가능)
            rooms -= 1
            j += 1
        else:
            # 새 방이 필요하다
            rooms += 1
            i += 1
        if rooms > max_rooms:
            max_rooms = rooms

    return max_rooms


# 입력 예시에 대한 예상 출력 (주석)
# min_meeting_rooms([(1, 2), (2, 3)])           -> 1   # 연달아 가능
# min_meeting_rooms([(1, 5), (2, 6), (3, 7)])   -> 3   # 전부 겹침
# min_meeting_rooms([(1, 3), (2, 4), (3, 5)])   -> 2   # [1,3]&[3,5] 한 방, [2,4] 다른 방
# min_meeting_rooms([(0, 30), (5, 10), (15, 20)]) -> 2
# min_meeting_rooms([(5, 10), (5, 8), (5, 6)])  -> 3   # 같은 시작시간
# min_meeting_rooms([(1, 10), (2, 5), (6, 9)])  -> 2   # 포함 관계


def run_tests(min_meeting_rooms):
    # 기본 케이스
    assert min_meeting_rooms([]) == 0
    assert min_meeting_rooms([(1, 2)]) == 1
    assert min_meeting_rooms([(1, 2), (2, 3)]) == 1  # 연달아 가능
    assert min_meeting_rooms([(1, 5), (2, 6), (3, 7)]) == 3  # 전부 겹침
    assert min_meeting_rooms([(1, 3), (2, 4), (3, 5)]) == 2  # [1,3]&[3,5] 한 방, [2,4] 다른 방
    assert min_meeting_rooms([(0, 30), (5, 10), (15, 20)]) == 2
    assert min_meeting_rooms([(1, 2), (1, 2), (1, 2), (1, 2)]) == 4

    # 엣지: 같은 시작시간
    assert min_meeting_rooms([(5, 10), (5, 8), (5, 6)]) == 3

    # 엣지: 한 회의가 다른 회의를 완전히 포함
    assert min_meeting_rooms([(1, 10), (2, 5), (6, 9)]) == 2

    # 큰 입력에서 정답만 확인 (성능 테스트는 별도)
    big = [(i, i + 1) for i in range(0, 100000, 2)]  # 전부 안 겹침
    assert min_meeting_rooms(big) == 1

    big2 = [(i, i + 100000) for i in range(100000)]  # 전부 겹침
    assert min_meeting_rooms(big2) == 100000

    print("모든 테스트 통과")


if __name__ == "__main__":
    run_tests(min_meeting_rooms)
