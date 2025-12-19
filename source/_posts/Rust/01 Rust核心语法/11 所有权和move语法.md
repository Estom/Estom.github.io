---
title: "11 所有权和move语法"
date: 1766125929
updated: 1766125929
tags: []
categories:
  - "Rust"
---

## 所有权

### 基本规则
* Rust 中的每一个值都有一个被称为其 所有者（owner）的变量。
* 值在任一时刻有且只有一个所有者。
* 当所有者（变量）离开作用域，这个值将被丢弃。

### 变量作用域

变量 s 绑定到了一个字符串字面量，这个字符串值是硬编码进程序代码中的。该变量从声明的那一刻开始直到当前 作用域 结束时都是有效的。
* 当 s 进入作用域 时，它就是有效的。
* 这一直持续到它 离开作用域 为止。
```rust
    {                      // s 在这里无效, 它尚未声明
        let s = "hello";   // 从此处起，s 开始有效

        // 使用 s
    }                      // 此作用域已结束，s 不再有效
```

### 内存分配

这是一个将 String 需要的内存返回给分配器的很自然的位置：当 s 离开作用域的时候。当变量离开作用域，Rust 为我们调用一个特殊的函数。这个函数叫做 drop，在这里 String 的作者可以放置释放内存的代码。Rust 在结尾的 } 处自动调用 drop。

```rust
    {
        let s = String::from("hello"); // 从此处起，s 开始有效

        // 使用 s
    }                                  // 此作用域已结束，
                                       // s 不再有效
```


### 堆上的数据：移动

```rust
  let s1 = String::from("hello");
    let s2 = s1;
```
在 let s2 = s1 之后，Rust 认为 s1 不再有效，因此 Rust 不需要在 s1 离开作用域后清理任何东西。
Rust 永远也不会自动创建数据的 “深拷贝”。因此，任何 自动 的复制可以被认为对运行时性能影响较小


### 克隆
我们 确实 需要深度复制 String 中堆上的数据，而不仅仅是栈上的数据，可以使用一个叫做 clone 的通用函数。
```rust
    let s1 = String::from("hello");
    let s2 = s1.clone();

    println!("s1 = {}, s2 = {}", s1, s2);
```
当出现 clone 调用时，你知道一些特定的代码被执行而且这些代码可能相当消耗资源。

### 只在栈上的数据：克隆

```rust
   let x = 5;
    let y = x;

    println!("x = {}, y = {}", x, y);
```
### 所有权与函数
将值传递给函数在语义上与给变量赋值相似。向函数传递值可能会移动或者复制，就像赋值语句一样。

```rust
fn main() {
  let s = String::from("hello");  // s 进入作用域

  takes_ownership(s);             // s 的值移动到函数里 ...
                                  // ... 所以到这里不再有效

  let x = 5;                      // x 进入作用域

  makes_copy(x);                  // x 应该移动函数里，
                                  // 但 i32 是 Copy 的，所以在后面可继续使用 x

} // 这里, x 先移出了作用域，然后是 s。但因为 s 的值已被移走，
  // 所以不会有特殊操作

fn takes_ownership(some_string: String) { // some_string 进入作用域
  println!("{}", some_string);
} // 这里，some_string 移出作用域并调用 `drop` 方法。占用的内存被释放

fn makes_copy(some_integer: i32) { // some_integer 进入作用域
  println!("{}", some_integer);
} // 这里，some_integer 移出作用域。不会有特殊操作
```

### 返回值与所有权

```rust
fn main() {
  let s1 = gives_ownership();         // gives_ownership 将返回值
                                      // 移给 s1

  let s2 = String::from("hello");     // s2 进入作用域

  let s3 = takes_and_gives_back(s2);  // s2 被移动到
                                      // takes_and_gives_back 中,
                                      // 它也将返回值移给 s3
} // 这里, s3 移出作用域并被丢弃。s2 也移出作用域，但已被移走，
  // 所以什么也不会发生。s1 移出作用域并被丢弃

fn gives_ownership() -> String {           // gives_ownership 将返回值移动给
                                           // 调用它的函数

  let some_string = String::from("yours"); // some_string 进入作用域

  some_string                              // 返回 some_string 并移出给调用的函数
}

// takes_and_gives_back 将传入字符串并返回该值
fn takes_and_gives_back(a_string: String) -> String { // a_string 进入作用域

  a_string  // 返回 a_string 并移出给调用的函数
}
```

变量的所有权总是遵循相同的模式：将值赋给另一个变量时移动它。当持有堆中数据值的变量离开作用域时，其值将通过 drop 被清理掉，除非数据被移动为另一个变量所有。




## 引用
### 基本规则
* 在任意给定时间，要么 只能有一个可变引用，要么 只能有多个不可变引用。
* 引用必须总是有效的。
### 引用定义
& 符号就是 引用，它们允许你使用值但不获取其所有权。

 借用（borrowing）创建一个引用的行为.

https://rustwiki.org/zh-CN/book/img/trpl04-05.svg

```rust
fn main() {
    let s1 = String::from("hello");

    let len = calculate_length(&s1);

    println!("The length of '{}' is {}.", s1, len);
}

fn calculate_length(s: &String) -> usize {
    s.len()
}
```
变量 s 有效的作用域与函数参数的作用域一样，不过当引用停止使用时并不丢弃它指向的数据，因为我们没有所有权。当函数使用引用而不是实际值作为参数，无需返回值来交还所有权，因为就不曾拥有所有权。

引用默认是不可变的。

### 可变引用

```rust
fn main() {
    let mut s = String::from("hello");

    change(&mut s);
}

fn change(some_string: &mut String) {
    some_string.push_str(", world");
}
```
将 s 改为 mut。然后必须在调用 change 函数的地方创建一个可变引用 &mut s，并更新函数签名以接受一个可变引用 some_string: &mut String。这就非常清楚地表明，change 函数将改变它所借用的值。

**规则一：** 在同一时间，只能有一个对某一特定数据的可变引用。尝试创建两个可变引用的代码将会失败。

```rust
 let mut s = String::from("hello");

    let r1 = &mut s;
    let r2 = &mut s;

    println!("{}, {}", r1, r2);
```
防止同一时间对同一数据进行多个可变引用的限制允许可变性，不过是以一种受限制的方式允许。新 Rustacean 们经常难以适应这一点，因为大部分语言中变量任何时候都是可变的。

这个限制的好处是 Rust 可以在编译时就避免数据竞争。数据竞争（data race）类似于竞态条件，它由这三个行为造成：

1. 两个或更多指针同时访问同一数据。
2. 至少有一个指针被用来写入数据。
3. 没有同步数据访问的机制。



可以使用大括号来创建一个新的作用域，以允许拥有多个可变引用，只是不能 同时 拥有：

```rust
   let mut s = String::from("hello");

    {
        let r1 = &mut s;
    } // r1 在这里离开了作用域，所以我们完全可以创建一个新的引用

    let r2 = &mut s;

```
**规则二：** 不能在拥有不可变引用的同时拥有可变引用。使用者可不希望不可变引用的值在他们的眼皮底下突然被改变了！然而，多个不可变引用是可以的，因为没有哪个只能读取数据的人有能力影响其他人读取到的数据。
* 读写和写写互斥存在
* 读读不互斥。

**规则三：** 引用的作用域从声明的地方开始一直持续到最后一次使用为止。例如，因为最后一次使用不可变引用（println!)，发生在声明可变引用之前，所以如下代码是可以编译的：

```rust
fn main() {
    let mut s = String::from("hello");

    let r1 = &s; // 没问题
    let r2 = &s; // 没问题
    println!("{} and {}", r1, r2);
    // 此位置之后 r1 和 r2 不再使用

    let r3 = &mut s; // 没问题
    println!("{}", r3);
}

```

### 悬垂引用
在具有指针的语言中，很容易通过释放内存时保留指向它的指针而错误地生成一个 悬垂指针（dangling pointer），所谓悬垂指针是其指向的内存可能已经被分配给其它持有者。相比之下，在 Rust 中编译器确保引用永远也不会变成悬垂状态：当你拥有一些数据的引用，编译器确保数据不会在其引用之前离开作用域。

让我们尝试创建一个悬垂引用，Rust 会通过一个编译时错误来避免：

```rust
fn main() {
    let reference_to_nothing = dangle();
}

fn dangle() -> &String {
    let s = String::from("hello");

    &s
}

```


在任意给定时间，要么 只能有一个可变引用，要么 只能有多个不可变引用。
引用必须总是有效的。


## 切片与引用
### 切片的使用


```rust
fn first_word(s: &String) -> &str {
    let bytes = s.as_bytes();

    for (i, &item) in bytes.iter().enumerate() {
        if item == b' ' {
            return &s[0..i];
        }
    }

    &s[..]
}
```
* 当调用 first_word 时，会返回与底层数据关联的单个值。这个值由一个 slice 开始位置的引用和 slice 中元素的数量组成。
* slice与String的声明周期相同

### 切片的作用


对于 Rust 的 .. range 语法，如果想要从索引 0 开始，可以不写两个点号之前的值。换句话说，如下两个语句是相同的：
```rust

#![allow(unused)]
fn main() {
let s = String::from("hello");

let slice = &s[0..2];
let slice = &s[..2];
}

```

依此类推，如果 slice 包含 String 的最后一个字节，也可以舍弃尾部的数字。这意味着如下也是相同的：
```rust

#![allow(unused)]
fn main() {
let s = String::from("hello");

let len = s.len();

let slice = &s[3..len];
let slice = &s[3..];
}

```

也可以同时舍弃这两个值来获取整个字符串的 slice。所以如下亦是相同的：

```rust

#![allow(unused)]
fn main() {
let s = String::from("hello");

let len = s.len();

let slice = &s[0..len];
let slice = &s[..];
}

```

### 实例
一下代码编译会报错
```rust
fn main() {
    let mut s = String::from("hello world");

    let word = first_word(&s);

    s.clear(); // error!

    println!("the first word is: {}", word);
}
```

```rust
$ cargo run
   Compiling ownership v0.1.0 (file:///projects/ownership)
error[E0502]: cannot borrow `s` as mutable because it is also borrowed as immutable
  --> src/main.rs:18:5
   |
16 |     let word = first_word(&s);
   |                           -- immutable borrow occurs here
17 | 
18 |     s.clear(); // error!
   |     ^^^^^^^^^ mutable borrow occurs here
19 | 
20 |     println!("the first word is: {}", word);
   |                                       ---- immutable borrow later used here

For more information about this error, try `rustc --explain E0502`.
error: could not compile `ownership` due to previous error

```

回忆一下借用规则，当拥有某值的不可变引用时，就不能再获取一个可变引用。因为 clear 需要清空 String，它尝试获取一个可变引用。在调用 clear 之后的 println! 使用了 word 中的引用，所以这个不可变的引用在此时必须仍然有效。Rust 不允许 clear 中的可变引用和 word 中的不可变引用同时存在，因此编译失败。Rust 不仅使得我们的 API 简单易用，也在编译时就消除了一整类的错误！

### 解释

* 字符串字面量就是 slice。这里 s 的类型是 &str：它是一个指向二进制程序特定位置的 slice。这也就是为什么字符串字面量是不可变的；&str 是一个不可变引用。
```rust

#![allow(unused)]
fn main() {
let s = "Hello, world!";
}

```

### 其他slice同理

字符串 slice，正如你想象的那样，是针对字符串的。不过也有更通用的 slice 类型。考虑一下这个数组：

```rust
let a = [1, 2, 3, 4, 5];

```


就跟我们想要获取字符串的一部分那样，我们也会想要引用数组的一部分。我们可以这样做：

```rust
let a = [1, 2, 3, 4, 5];
let slice = &a[1..3];
```

这个 slice 的类型是 &[i32]。它跟字符串 slice 的工作方式一样，通过存储第一个集合元素的引用和一个集合总长度。你可以对其他所有集合使用这类 slice。



## 所有权深入理解

人生就是用代价换好处，跟咒术回战中的天与咒缚一样，牺牲的东西越多，能换到的能力就越多，都是等价交换。

Rust中的所有权机制，就是牺牲灵活性换取安全性。

### 值语义和引用语义

值语义会发生拷贝
引用语义会发生移动

### 表达式规则

1. 左值，在Rust中又称为，位置表达式
2. 右值，在Rust中又称为，值表达式
3. 左值一定是右值，因为位置表达式可以独立作为一个值表达式，被赋值语句使用。
4. 函数的返回值一定是右值。

### 规则一：所有权规则：何时发生移动

1. 左值出现在右值表达式中，或者说，位置表达式出现在值表达式中。
2. 左值没有实现Copy trait。
   1. 如果左值实现了Copy trait，那么左值就是发生复制，因为Copy trait表明左值可以复制，而不是移动。
   2. 如果左值实现了Drop trait，那么左值就是发生移动，因为Drop trait表明左值可以移动，而不是销毁。
   3. 这两个trait必须且仅能存在一个。


### 规则二：生命周期规则：变量与数据生命周期一致

RAII销毁变量的同时销毁资源

basically, RAII is a design pattern that guarantees that resources are cleaned up in the right way.
1. 一个数据只能被一个变量所拥有。
2. 只有持有数据所有权的变量才会释放它的资源

### 规则三：借用规则
简单理解为一个代码层面的读写锁。写独占，读共享
1. 一个变量允许存在多个不可变借用，或一个可变借用。（写写互斥）
2. 如果存在不可变借用，所有者暂时失去写权限，只能读取。（读读共享）
3. 如果存在可变借用，所有者暂时失去读写权限。（读写互斥）
4. 只要存在任意借用，所有者暂时失去了释放与移动的权限。（写写、读写互斥）


另外有一点很重要，借用是C++中的指针，是取地址操作运算符！可以解引用。


### 重新借用

遵循规则一：所有权规则。重新借用后所有权转移到新的借用中。


### 复合类型的所有权

1. 聚合所有权，整体共享一套所有权规则。数组
2. 字段所有类型，复合类型的字段独享所有权。结构体
