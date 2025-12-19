---
title: "04 Queue"
date: 1766125929
updated: 1766125929
tags: []
categories:
  - "Java"
---

# Queue


## 0 Queue介绍

### 主要方法
`Queue`队列，在 JDK 中有两种不同类型的集合实现：**单向队列**（AbstractQueue） 和 **双端队列**（Deque）

![img](https://cdn.nlark.com/yuque/0/2020/png/1694029/1595684241064-e863aeca-6a95-4423-92c4-762f56be1dbe.png)

Queue 中提供了两套增加、删除元素的 API，当插入或删除元素失败时，会有**两种不同的失败处理策略**。

| 方法及失败策略 | 插入方法 | 删除方法 | 查找方法 |
| :------------- | :------- | :------- | -------- |
| 抛出异常       | add()    | remove() | get()    |
| 返回失败默认值 | offer()  | poll()   | peek()   |

选取哪种方法的决定因素：插入和删除元素失败时，希望`抛出异常`还是返回`布尔值`

`add()` 和 `offer()` 对比：

在队列长度大小确定的场景下，队列放满元素后，添加下一个元素时，add() 会抛出 `IllegalStateException`异常，而 `offer()` 会返回 `false` 。

但是它们两个方法在插入**某些不合法的元素**时都会抛出三个相同的异常。

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1595691512036-ed9fd3ea-5432-4105-a3fb-a5374d571971.png)

`remove()` 和 `poll()` 对比：

在**队列为空**的场景下， `remove()` 会抛出 `NoSuchElementException`异常，而 `poll()` 则返回 `null` 。

`get()`和`peek()`对比：

在队列为空的情况下，`get()`会抛出`NoSuchElementException`异常，而`peek()`则返回`null`。


### Deque 接口

`Deque` 接口的实现非常好理解：从**单向**队列演变为**双向**队列，内部额外提供**双向队列的操作方法**即可：

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1596166722772-975ff644-6abf-441b-b678-4a6de5b0eef1.png)

Deque 接口额外提供了**针对队列的头结点和尾结点**操作的方法，而**插入、删除方法同样也提供了两套不同的失败策略**。除了`add()`和`offer()`，`remove()`和`poll()`以外，还有`get()`和`peek()`出现了不同的策略

### AbstractQueue 抽象类

AbstractQueue 类中提供了各个 API 的基本实现，主要针对各个不同的处理策略给出基本的方法实现，定义在这里的作用是让`子类`根据其`方法规范`（操作失败时抛出异常还是返回默认值）实现具体的业务逻辑。

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1596167156067-36121579-8127-4019-ba47-e4de73f05cda.png)


## 1 LinkedList :warning: 已废弃

### 继承关系

![](image/2022-12-15-16-55-23.png)

### 底层实现

LinkedList 底层采用`双向链表`数据结构存储元素，由于链表的内存地址`非连续`，所以它不具备随机访问的特点，但由于它利用指针连接各个元素，所以插入、删除元素只需要`操作指针`，不需要`移动元素`，故具有**增删快、查询慢**的特点。它也是一个非线程安全的集合。

![](image/2022-12-15-16-54-49.png)



由于以双向链表作为数据结构，它是**线程不安全**的集合；存储的每个节点称为一个`Node`，下图可以看到 Node 中保存了`next`和`prev`指针，`item`是该节点的值。在插入和删除时，时间复杂度都保持为 `O(1)`

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1595725358023-1f64f780-9dd0-47ff-a84c-d4101d16c1e1.png)

关于 LinkedList，除了它是以链表实现的集合外，还有一些特殊的特性需要注意的。

- 优势：LinkedList 底层没有`扩容机制`，使用`双向链表`存储元素，所以插入和删除元素效率较高，适用于频繁操作元素的场景
- 劣势：LinkedList 不具备`随机访问`的特点，查找某个元素只能从 `head` 或 `tail` 指针一个一个比较，所以**查找中间的元素时效率很低**
- 查找优化：LinkedList 查找某个下标 `index` 的元素时**做了优化**，若 `index > (size / 2)`，则从 `head` 往后查找，否则从 `tail` 开始往前查找，代码如下所示：

```Java
LinkedList.Node<E> node(int index) {
    LinkedList.Node x;
    int i;
    if (index < this.size >> 1) { // 查找的下标处于链表前半部分则从头找
        x = this.first;
        for(i = 0; i < index; ++i) { x = x.next; }
        return x;
    } else { // 查找的下标处于数组的后半部分则从尾开始找
        x = this.last;
        for(i = this.size - 1; i > index; --i) { x = x.prev; }
        return x;
    }
}
```

- 双端队列：使用双端链表实现，并且实现了 `Deque` 接口，使得 LinkedList 可以用作**双端队列**。下图可以看到 Node 是集合中的元素，提供了前驱指针和后继指针，还提供了一系列操作`头结点`和`尾结点`的方法，具有双端队列的特性。

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1595693779116-a8156f03-36fa-4557-892e-ea5103b06136.png)

LinkedList 集合最让人树枝的是它的链表结构，但是我们同时也要注意它是一个双端队列型的集合。

```java
Deque<Object> deque = new LinkedList<>();
```

### 常用方法


```java
LinkedList() ：初始化一个空的LinkedList实现。
LinkedListExample(Collection c) ：初始化一个LinkedList，该LinkedList包含指定集合的​​元素，并按集合的迭代器返回它们的顺序。
boolean add(Object o) ：将指定的元素追加到列表的末尾。
void add（int index，Object element） ：将指定的元素插入列表中指定位置的索引处。
void addFirst(Object o) ：将给定元素插入列表的开头。
void addLast(Object o) ：将给定元素附加到列表的末尾。
int size() ：返回列表中的元素数
boolean contains(Object o) ：如果列表包含指定的元素，则返回true ，否则返回false 。
boolean remove(Object o) ：删除列表中指定元素的第一次出现。
Object getFirst() ：返回列表中的第一个元素。
Object getLast() ：返回列表中的最后一个元素。
int indexOf(Object o) ：返回指定元素首次出现的列表中的索引；如果列表不包含指定元素，则返回-1。
lastIndexOf(Object o) ：返回指定元素最后一次出现的列表中的索引；如果列表不包含指定元素，则返回-1。
Iterator iterator() ：以适当的顺序返回对该列表中的元素进行迭代的迭代器。
Object[] toArray() ：以正确的顺序返回包含此列表中所有元素的数组。
List subList（int fromIndex，int toIndex） ：返回此列表中指定的fromIndex（包括）和toIndex（不包括）之间的视图。
```

### LinkedList与ArrayList

* ArrayList是使用动态可调整大小的数组的概念实现的。 而LinkedList是双向链表实现。
* ArrayList允许随机访问其元素，而LinkedList则不允许。
* LinkedList还实现了Queue接口，该接口添加了比ArrayList更多的方法，例如offer（），peek（），poll（）等。
* 与LinkedList相比， ArrayList添加和删​​除速度较慢，但​​在获取时却较快，因为如果LinkedList中的array已满，则无需调整数组大小并将内容复制到新数组。
* LinkedList比ArrayList具有更多的内存开销，因为在ArrayList中，每个索引仅保存实际对象，但是在LinkedList的情况下，每个节点都保存下一个和上一个节点的数据和地址。


## 2 ArrayDeque

使用**数组**实现的双端队列，它是**无界**的双端队列，最小的容量是`8`（JDK 1.8）。在 JDK 11 看到它默认容量已经是 `16`了。

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1595695213834-cb4f1c3a-e07a-42aa-981f-31a896febe26.png)

`ArrayDeque` 在日常使用得不多，值得注意的是它与 `LinkedList` 的对比：`LinkedList` 采用**链表**实现双端队列，而 `ArrayDeque` 使用**数组**实现双端队列。

> 在文档中作者写到：**ArrayDeque 作为栈时比 Stack 性能好，作为队列时比 LinkedList 性能好**

由于双端队列**只能在头部和尾部**操作元素，所以删除元素和插入元素的时间复杂度大部分都稳定在 `O(1)` ，除非在扩容时会涉及到元素的批量复制操作。但是在大多数情况下，使用它时应该指定一个大概的数组长度，避免频繁的扩容。


## 3 PriorityQueue
### 底层原理
PriorityQueue 基于**优先级堆实现**的优先级队列，而堆是采用**数组**实现：

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1595727271522-d144468c-041e-4721-a786-9f952f06fafe.png)

文档中的描述告诉我们：该数组中的元素通过传入 `Comparator` 进行定制排序，如果不传入`Comparator`时，则按照元素本身`自然排序`，但要求元素实现了`Comparable`接口，所以 PriorityQueue **不允许存储 NULL 元素**。

PriorityQueue 应用场景：元素本身具有优先级，需要按照**优先级处理元素**

- 例如游戏中的VIP玩家与普通玩家，VIP 等级越高的玩家越先安排进入服务器玩耍，减少玩家流失。

```Java
public static void main(String[] args) {
    Student vip1 = new Student("张三", 1);
    Student vip3 = new Student("洪七", 2);
    Student vip4 = new Student("老八", 4);
    Student vip2 = new Student("李四", 1);
    Student normal1 = new Student("王五", 0);
    Student normal2 = new Student("赵六", 0);
    // 根据玩家的 VIP 等级进行降序排序
    PriorityQueue<Student> queue = new PriorityQueue<>((o1, o2) ->  o2.getScore().compareTo(o1.getScore()));
    queue.add(vip1);queue.add(vip4);queue.add(vip3);
    queue.add(normal1);queue.add(normal2);queue.add(vip2);
    while (!queue.isEmpty()) {
        Student s1 = queue.poll();
        System.out.println(s1.getName() + "进入游戏; " + "VIP等级: " + s1.getScore());
    }
}
 public static class Student implements Comparable<Student> {
     private String name;
     private Integer score;
     public Student(String name, Integer score) {
         this.name = name;
         this.score = score;
     }
     @Override
     public int compareTo(Student o) {
         return this.score.compareTo(o.getScore());
     }
 }
```

执行上面的代码可以得到下面这种有趣的结果，可以看到`氪金`使人带来快乐。

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1595727945968-768b45bb-96dc-4850-8759-f07776107a23.png)

VIP 等级越高（优先级越高）就越优先安排进入游戏（优先处理），类似这种有优先级的场景还有非常多，各位可以发挥自己的想象力。

PriorityQueue 总结：

- PriorityQueue 是基于**优先级堆**实现的优先级队列，而堆是用**数组**维护的

- PriorityQueue 适用于**元素按优先级处理**的业务场景，例如用户在请求人工客服需要排队时，根据用户的**VIP等级**进行 `插队` 处理，等级越高，越先安排客服。


### 主要方法
```java
boolean add(object) ：将指定的元素插入此优先级队列。
boolean offer(object) ：将指定的元素插入此优先级队列。
boolean remove(object) ：从此队列中移除指定元素的单个实例（如果存在）。
Object poll() ：检索并删除此队列的头部；如果此队列为空，则返回null。
Object element() ：获取但不删除此队列的头部，如果此队列为空，则抛出NoSuchElementException 。
Object peek() ：检索但不删除此队列的头部；如果此队列为空，则返回null。
void clear() ：从此优先级队列中删除所有元素。
Comparator comparator() ：返回用于对此队列中的元素进行排序的Comparator comparator()如果此队列是根据其元素的自然顺序排序的，则返回null。
boolean contains(Object o) ：如果此队列包含指定的元素，则返回true。
Iterator iterator() ：返回对该队列中的元素进行迭代的迭代器。
int size() ：返回此队列中的元素数。
Object[] toArray() ：返回一个包含此队列中所有元素的数组。
```
