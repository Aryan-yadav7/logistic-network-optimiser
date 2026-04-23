def merge_sort(arr, key):
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = merge_sort(arr[:mid], key)
    right = merge_sort(arr[mid:], key)

    return merge(left, right, key)


def merge(left, right, key):
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result

def sort_by_deadline(packages):
    return merge_sort(packages, key=lambda p: p["deadline"])

def quick_sort(arr, key, low=None, high=None):
    if low is None: low = 0
    if high is None: high = len(arr) - 1

    if low < high:
        pi = partition(arr, key, low, high)
        quick_sort(arr, key, low, pi - 1)
        quick_sort(arr, key, pi + 1, high)

    return arr


def partition(arr, key, low, high):
    pivot = arr[high]
    i = low - 1

    for j in range(low, high):
        if key(arr[j]) <= key(pivot):
            i += 1
            arr[i], arr[j] = arr[j], arr[i]

    arr[i + 1], arr[high] = arr[high], arr[i + 1]
    return i + 1


def heap_sort(arr, key):
    n = len(arr)

    for i in range(n // 2 - 1, -1, -1):
        heapify(arr, n, i, key)

    for i in range(n - 1, 0, -1):
        arr[0], arr[i] = arr[i], arr[0]
        heapify(arr, i, 0, key)

    return arr


def heapify(arr, n, i, key):
    largest = i
    left = 2 * i + 1
    right = 2 * i + 2

    if left < n and key(arr[left]) > key(arr[largest]):
        largest = left

    if right < n and key(arr[right]) > key(arr[largest]):
        largest = right

    if largest != i:
        arr[i], arr[largest] = arr[largest], arr[i]
        heapify(arr, n, largest, key)


def bubble_sort(arr, key):
    n = len(arr)

    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if key(arr[j]) > key(arr[j + 1]):
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break

    return arr