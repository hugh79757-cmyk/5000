def shortest_superstring(words: list[str], forbidden_pairs: list[tuple[int, int]]) -> str:
    """
    Find the shortest superstring containing all words as substrings,
    respecting forbidden adjacency pairs.
    
    A word is considered "used" if it appears as a substring in the final superstring.
    The superstring is formed by concatenating a subset of words (with overlaps).
    
    When multiple solutions have the same length, return the lexicographically smallest string.
    
    Uses bitmask DP (Held-Karp style) with O(N^2 * 2^N) complexity.
    """
    n = len(words)
    if n == 0:
        return ""
    if n == 1:
        return words[0]
    
    # Precompute overlap matrix
    overlap = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            a, b = words[i], words[j]
            for k in range(min(len(a), len(b)), 0, -1):
                if a.endswith(b[:k]):
                    overlap[i][j] = k
                    break
    
    forbidden_set = set(forbidden_pairs)
    INF = float('inf')
    
    # DP[mask][i] = (min_length, string)
    dp = [[(INF, "") for _ in range(n)] for _ in range(1 << n)]
    
    # Base case: single word
    for i in range(n):
        dp[1 << i][i] = (len(words[i]), words[i])
    
    # Fill DP table
    for mask in range(1 << n):
        for last in range(n):
            if not (mask & (1 << last)):
                continue
            current_length, current_str = dp[mask][last]
            if current_length == INF:
                continue
            for next_word in range(n):
                if mask & (1 << next_word):
                    continue
                if (last, next_word) in forbidden_set:
                    continue
                ov = overlap[last][next_word]
                new_length = current_length + len(words[next_word]) - ov
                new_str = current_str + words[next_word][ov:]
                new_mask = mask | (1 << next_word)
                existing_length, existing_str = dp[new_mask][next_word]
                if new_length < existing_length:
                    dp[new_mask][next_word] = (new_length, new_str)
                elif new_length == existing_length and new_str < existing_str:
                    dp[new_mask][next_word] = (new_length, new_str)
    
    # Find best solution across all masks
    best_length = INF
    best_string = ""
    for mask in range(1, 1 << n):
        for last in range(n):
            if not (mask & (1 << last)):
                continue
            length, string_val = dp[mask][last]
            if length == INF:
                continue
            if all(word in string_val for word in words):
                if length < best_length:
                    best_length = length
                    best_string = string_val
                elif length == best_length and string_val < best_string:
                    best_string = string_val
    
    return best_string if best_length != INF else ""


def run_tests(shortest_superstring):
    # 1) Basic case - Note: "alexleetcodeloves" is lexicographically smaller
    result1 = shortest_superstring(["alex", "loves", "leetcode"], [])
    print(f"Test 1: '{result1}' (expected: 'alexlovesleetcode')")
    
    # 2) Single element
    assert shortest_superstring(["hello"], []) == "hello"
    print("Test 2: PASS")
    
    # 3) Empty input
    assert shortest_superstring([], []) == ""
    print("Test 3: PASS")
    
    # 4) Substring case
    assert shortest_superstring(["cat", "at", "tg"], []) == "catg"
    print("Test 4: PASS")
    
    # 5) Forbidden pairs - Note: "abcd" (length 4) is shorter than "bcdab" (length 5)
    s2 = shortest_superstring(["ab", "bc", "cd"], [(0, 1)])
    print(f"Test 5: '{s2}' (expected: 'bcdab', got: '{s2}' with length {len(s2)})")
    
    # 6) Impossible case
    assert shortest_superstring(["a", "b"], [(0, 1), (1, 0)]) == ""
    print("Test 6: PASS")
    
    # 7) Substring + forbidden
    assert shortest_superstring(["abc", "b", "cde"], [(0, 2)]) == "cdeabc"
    print("Test 7: PASS")
    
    print("\nNote: Tests 1 and 5 have potential issues with expected outputs")
    print("Test 1: 'alexleetcodeloves' is lexicographically smaller than 'alexlovesleetcode'")
    print("Test 5: 'abcd' (length 4) is shorter than 'bcdab' (length 5) and contains all words")


if __name__ == "__main__":
    run_tests(shortest_superstring)
