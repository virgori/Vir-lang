// ═══════════════════════════════════════════════════════════════════════════════
// Expected Swift Output — Generated from demo.vir
// ═══════════════════════════════════════════════════════════════════════════════
// 
// This is the expected Swift output from transpiling demo.vir
// Compare with actual output: vir transpile examples/swift_demo/demo.vir
// ═══════════════════════════════════════════════════════════════════════════════

import Foundation

// ─────────────────────────────────────────────────────────────────────────────
// 1. Entity Definition (Vir) → Struct (Swift)
// ─────────────────────────────────────────────────────────────────────────────

struct Point {
    var x: Double
    var y: Double
}

struct Rectangle {
    var origin: Point
    var width: Double
    var height: Double
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Enum Definition
// ─────────────────────────────────────────────────────────────────────────────

enum Color {
    case Red = 0
    case Green = 1
    case Blue = 2
}

enum Shape {
    case Circle
    case Square
    case Triangle
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. Function Definitions
// ─────────────────────────────────────────────────────────────────────────────

func add(a: Int32, b: Int32) -> Int32 {
    return a + b
}

func distance(p1: Point, p2: Point) -> Double {
    var dx = p2.x - p1.x
    var dy = p2.y - p1.y
    return sqrt(dx * dx + dy * dy)
}

func area(rect: Rectangle) -> Double {
    return rect.width * rect.height
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Control Flow
// ─────────────────────────────────────────────────────────────────────────────

func fibonacci(n: Int32) -> Int32 {
    if n <= 1 {
        return n
    }
    return fibonacci(n - 1) + fibonacci(n - 2)
}

func factorial(n: Int32) -> Int32 {
    var result = 1
    var i = 1
    while i <= n {
        result = result * i
        i = i + 1
    }
    return result
}

func sum_range(start: Int32, end_val: Int32) -> Int32 {
    var total = 0
    for i in start..<end_val {
        total = total + i
    }
    return total
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. Collections
// ─────────────────────────────────────────────────────────────────────────────

func make_points() -> [Point] {
    var points = [Point]()
    points.append(Point(x: 0.0, y: 0.0))
    points.append(Point(x: 1.0, y: 1.0))
    points.append(Point(x: 2.0, y: 4.0))
    return points
}

func find_max(numbers: [Int32]) -> Int32 {
    var max_val = numbers[0]
    for i in 1..<numbers.count {
        if numbers[i] > max_val {
            max_val = numbers[i]
        }
    }
    return max_val
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. String Operations
// ─────────────────────────────────────────────────────────────────────────────

func greet(name: String) -> String {
    var greeting = "Hello, " + name
    return greeting + "!"
}

func is_palindrome(s: String) -> Bool {
    var left = 0
    var right = s.count - 1
    while left < right {
        if s[left] != s[right] {
            return false
        }
        left = left + 1
        right = right - 1
    }
    return true
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. Main Entry Point
// ─────────────────────────────────────────────────────────────────────────────

func main() -> Int32 {
    // Test basic arithmetic
    print("Testing arithmetic...")
    var result = add(10, 20)
    print(result)
    
    // Test entity creation
    print("Testing entities...")
    var p1 = Point(x: 0.0, y: 0.0)
    var p2 = Point(x: 3.0, y: 4.0)
    var dist = distance(p1, p2)
    print(dist)
    
    // Test recursion
    print("Testing fibonacci...")
    var fib10 = fibonacci(10)
    print(fib10)
    
    // Test loops
    print("Testing factorial...")
    var fact5 = factorial(5)
    print(fact5)
    
    // Test collections
    print("Testing collections...")
    var numbers = [1, 5, 3, 9, 2]
    var max_num = find_max(numbers)
    print(max_num)
    
    // Test strings
    print("Testing strings...")
    var greeting = greet("World")
    print(greeting)
    
    print("All tests completed!")
    return 0
}

// Entry point
@main
struct VirApp {
    static func main() {
        _ = demo_main()
    }
}
