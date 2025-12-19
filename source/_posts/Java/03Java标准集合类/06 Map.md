---
title: "06 Map"
date: 1766125929
updated: 1766125929
tags: []
categories:
  - "Java"
---


## 0 Map 集合体系详解

`Map`接口是由`<key, value>`组成的集合，由`key`映射到**唯一**的`value`，所以`Map`不能包含重复的`key`，每个键**至多**映射一个值。下图是整个 Map 集合体系的主要组成部分，我将会按照日常使用频率从高到低一一讲解。

不得不提的是 Map 的设计理念：**定位元素**的时间复杂度优化到 `O(1)`

Map 体系下主要分为 AbstractMap 和 SortedMap两类集合

`AbstractMap`是对 Map 接口的扩展，它定义了普通的 Map 集合具有的**通用行为**，可以避免子类重复编写大量相同的代码，子类继承 AbstractMap 后可以重写它的方法，**实现额外的逻辑**，对外提供更多的功能。

`SortedMap` 定义了该类 Map 具有 `排序`行为，同时它在内部定义好有关排序的抽象方法，当子类实现它时，必须重写所有方法，对外提供排序功能。

![](image/2022-12-15-19-35-52.png)

## 1 HashMap

### 底层原理
HashMap 是一个**最通用的**利用哈希表存储元素的集合，将元素放入 HashMap 时，将`key`的哈希值转换为数组的`索引`下标**确定存放位置**，查找时，根据`key`的哈希地址转换成数组的`索引`下标**确定查找位置**。

HashMap 底层是用数组 + 链表 + 红黑树这三种数据结构实现，它是**非线程安全**的集合。

![](image/2022-12-15-19-38-24.png)

发送哈希冲突时，HashMap 的解决方法是将相同映射地址的元素连成一条`链表`，如果链表的长度大于`8`时，且数组的长度大于`64`则会转换成`红黑树`数据结构。

关于 HashMap 的简要总结：

1. 它是集合中最常用的`Map`集合类型，底层由`数组 + 链表 + 红黑树`组成
2. HashMap不是线程安全的
3. 插入元素时，通过计算元素的`哈希值`，通过**哈希映射函数**转换为`数组下标`；查找元素时，同样通过哈希映射函数得到数组下标`定位元素的位置`


#### 1. 存储结构

内部包含了一个 Entry 类型的数组 table。Entry 存储着键值对。它包含了四个字段，从 next 字段我们可以看出 Entry 是一个链表。即数组中的每个位置被当成一个桶，一个桶存放一个链表。HashMap 使用拉链法来解决冲突，同一个链表中存放哈希值和散列桶取模运算结果相同的 Entry。

<div align="center"> <img src="https://cs-notes-1256109796.cos.ap-guangzhou.myqcloud.com/image-20191208234948205.png"/> </div><br>

```java
transient Entry[] table;
```

```java
static class Entry<K,V> implements Map.Entry<K,V> {
    final K key;
    V value;
    Entry<K,V> next;
    int hash;

    Entry(int h, K k, V v, Entry<K,V> n) {
        value = v;
        next = n;
        key = k;
        hash = h;
    }

    public final K getKey() {
        return key;
    }

    public final V getValue() {
        return value;
    }

    public final V setValue(V newValue) {
        V oldValue = value;
        value = newValue;
        return oldValue;
    }

    public final boolean equals(Object o) {
        if (!(o instanceof Map.Entry))
            return false;
        Map.Entry e = (Map.Entry)o;
        Object k1 = getKey();
        Object k2 = e.getKey();
        if (k1 == k2 || (k1 != null && k1.equals(k2))) {
            Object v1 = getValue();
            Object v2 = e.getValue();
            if (v1 == v2 || (v1 != null && v1.equals(v2)))
                return true;
        }
        return false;
    }

    public final int hashCode() {
        return Objects.hashCode(getKey()) ^ Objects.hashCode(getValue());
    }

    public final String toString() {
        return getKey() + "=" + getValue();
    }
}
```

#### 2. 拉链法的工作原理

```java
HashMap<String, String> map = new HashMap<>();
map.put("K1", "V1");
map.put("K2", "V2");
map.put("K3", "V3");
```

- 新建一个 HashMap，默认大小为 16；
- 插入 &lt;K1,V1\> 键值对，先计算 K1 的 hashCode 为 115，使用除留余数法得到所在的桶下标 115%16=3。
- 插入 &lt;K2,V2\> 键值对，先计算 K2 的 hashCode 为 118，使用除留余数法得到所在的桶下标 118%16=6。
- 插入 &lt;K3,V3\> 键值对，先计算 K3 的 hashCode 为 118，使用除留余数法得到所在的桶下标 118%16=6，插在 &lt;K2,V2\> 前面。

应该注意到链表的插入是以头插法方式进行的，例如上面的 &lt;K3,V3\> 不是插在 &lt;K2,V2\> 后面，而是插入在链表头部。

查找需要分成两步进行：

- 计算键值对所在的桶；
- 在链表上顺序查找，时间复杂度显然和链表的长度成正比。

<div align="center"> <img src="https://cs-notes-1256109796.cos.ap-guangzhou.myqcloud.com/image-20191208235258643.png"/> </div><br>

#### 3. put 操作

```java
public V put(K key, V value) {
    if (table == EMPTY_TABLE) {
        inflateTable(threshold);
    }
    // 键为 null 单独处理
    if (key == null)
        return putForNullKey(value);
    int hash = hash(key);
    // 确定桶下标
    int i = indexFor(hash, table.length);
    // 先找出是否已经存在键为 key 的键值对，如果存在的话就更新这个键值对的值为 value
    for (Entry<K,V> e = table[i]; e != null; e = e.next) {
        Object k;
        if (e.hash == hash && ((k = e.key) == key || key.equals(k))) {
            V oldValue = e.value;
            e.value = value;
            e.recordAccess(this);
            return oldValue;
        }
    }

    modCount++;
    // 插入新键值对
    addEntry(hash, key, value, i);
    return null;
}
```

HashMap 允许插入键为 null 的键值对。但是因为无法调用 null 的 hashCode() 方法，也就无法确定该键值对的桶下标，只能通过强制指定一个桶下标来存放。HashMap 使用第 0 个桶存放键为 null 的键值对。

```java
private V putForNullKey(V value) {
    for (Entry<K,V> e = table[0]; e != null; e = e.next) {
        if (e.key == null) {
            V oldValue = e.value;
            e.value = value;
            e.recordAccess(this);
            return oldValue;
        }
    }
    modCount++;
    addEntry(0, null, value, 0);
    return null;
}
```

使用链表的头插法，也就是新的键值对插在链表的头部，而不是链表的尾部。

```java
void addEntry(int hash, K key, V value, int bucketIndex) {
    if ((size >= threshold) && (null != table[bucketIndex])) {
        resize(2 * table.length);
        hash = (null != key) ? hash(key) : 0;
        bucketIndex = indexFor(hash, table.length);
    }

    createEntry(hash, key, value, bucketIndex);
}

void createEntry(int hash, K key, V value, int bucketIndex) {
    Entry<K,V> e = table[bucketIndex];
    // 头插法，链表头部指向新的键值对
    table[bucketIndex] = new Entry<>(hash, key, value, e);
    size++;
}
```

```java
Entry(int h, K k, V v, Entry<K,V> n) {
    value = v;
    next = n;
    key = k;
    hash = h;
}
```

#### 4. 确定桶下标

很多操作都需要先确定一个键值对所在的桶下标。

```java
int hash = hash(key);
int i = indexFor(hash, table.length);
```

**4.1 计算 hash 值**  

```java
final int hash(Object k) {
    int h = hashSeed;
    if (0 != h && k instanceof String) {
        return sun.misc.Hashing.stringHash32((String) k);
    }

    h ^= k.hashCode();

    // This function ensures that hashCodes that differ only by
    // constant multiples at each bit position have a bounded
    // number of collisions (approximately 8 at default load factor).
    h ^= (h >>> 20) ^ (h >>> 12);
    return h ^ (h >>> 7) ^ (h >>> 4);
}
```

```java
public final int hashCode() {
    return Objects.hashCode(key) ^ Objects.hashCode(value);
}
```

**4.2 取模**  

令 x = 1\<\<4，即 x 为 2 的 4 次方，它具有以下性质：

```
x   : 00010000
x-1 : 00001111
```

令一个数 y 与 x-1 做与运算，可以去除 y 位级表示的第 4 位以上数：

```
y       : 10110010
x-1     : 00001111
y&(x-1) : 00000010
```

这个性质和 y 对 x 取模效果是一样的：

```
y   : 10110010
x   : 00010000
y%x : 00000010
```

我们知道，位运算的代价比求模运算小的多，因此在进行这种计算时用位运算的话能带来更高的性能。

确定桶下标的最后一步是将 key 的 hash 值对桶个数取模：hash%capacity，如果能保证 capacity 为 2 的 n 次方，那么就可以将这个操作转换为位运算。

```java
static int indexFor(int h, int length) {
    return h & (length-1);
}
```

#### 5. 扩容-基本原理

设 HashMap 的 table 长度为 M，需要存储的键值对数量为 N，如果哈希函数满足均匀性的要求，那么每条链表的长度大约为 N/M，因此查找的复杂度为 O(N/M)。

为了让查找的成本降低，应该使 N/M 尽可能小，因此需要保证 M 尽可能大，也就是说 table 要尽可能大。HashMap 采用动态扩容来根据当前的 N 值来调整 M 值，使得空间效率和时间效率都能得到保证。

和扩容相关的参数主要有：capacity、size、threshold 和 load_factor。

| 参数 | 含义 |
| :--: | :-- |
| capacity | table 的容量大小，默认为 16。需要注意的是 capacity 必须保证为 2 的 n 次方。|
| size | 键值对数量。 |
| threshold | size 的临界值，当 size 大于等于 threshold 就必须进行扩容操作。 |
| loadFactor | 装载因子，table 能够使用的比例，threshold = (int)(capacity* loadFactor)。 |

```java
static final int DEFAULT_INITIAL_CAPACITY = 16;

static final int MAXIMUM_CAPACITY = 1 << 30;

static final float DEFAULT_LOAD_FACTOR = 0.75f;

transient Entry[] table;

transient int size;

int threshold;

final float loadFactor;

transient int modCount;
```

从下面的添加元素代码中可以看出，当需要扩容时，令 capacity 为原来的两倍。

```java
void addEntry(int hash, K key, V value, int bucketIndex) {
    Entry<K,V> e = table[bucketIndex];
    table[bucketIndex] = new Entry<>(hash, key, value, e);
    if (size++ >= threshold)
        resize(2 * table.length);
}
```

扩容使用 resize() 实现，需要注意的是，扩容操作同样需要把 oldTable 的所有键值对重新插入 newTable 中，因此这一步是很费时的。

```java
void resize(int newCapacity) {
    Entry[] oldTable = table;
    int oldCapacity = oldTable.length;
    if (oldCapacity == MAXIMUM_CAPACITY) {
        threshold = Integer.MAX_VALUE;
        return;
    }
    Entry[] newTable = new Entry[newCapacity];
    transfer(newTable);
    table = newTable;
    threshold = (int)(newCapacity * loadFactor);
}

void transfer(Entry[] newTable) {
    Entry[] src = table;
    int newCapacity = newTable.length;
    for (int j = 0; j < src.length; j++) {
        Entry<K,V> e = src[j];
        if (e != null) {
            src[j] = null;
            do {
                Entry<K,V> next = e.next;
                int i = indexFor(e.hash, newCapacity);
                e.next = newTable[i];
                newTable[i] = e;
                e = next;
            } while (e != null);
        }
    }
}
```

#### 6. 扩容-重新计算桶下标

在进行扩容时，需要把键值对重新计算桶下标，从而放到对应的桶上。在前面提到，HashMap 使用 hash%capacity 来确定桶下标。HashMap capacity 为 2 的 n 次方这一特点能够极大降低重新计算桶下标操作的复杂度。

假设原数组长度 capacity 为 16，扩容之后 new capacity 为 32：

```html
capacity     : 00010000
new capacity : 00100000
```

对于一个 Key，它的哈希值 hash 在第 5 位：

- 为 0，那么 hash%00010000 = hash%00100000，桶位置和原来一致；
- 为 1，hash%00010000 = hash%00100000 + 16，桶位置是原位置 + 16。

#### 7. 计算数组容量

HashMap 构造函数允许用户传入的容量不是 2 的 n 次方，因为它可以自动地将传入的容量转换为 2 的 n 次方。

先考虑如何求一个数的掩码，对于 10010000，它的掩码为 11111111，可以使用以下方法得到：

```
mask |= mask >> 1    11011000
mask |= mask >> 2    11111110
mask |= mask >> 4    11111111
```

mask+1 是大于原始数字的最小的 2 的 n 次方。

```
num     10010000
mask+1 100000000
```

以下是 HashMap 中计算数组容量的代码：

```java
static final int tableSizeFor(int cap) {
    int n = cap - 1;
    n |= n >>> 1;
    n |= n >>> 2;
    n |= n >>> 4;
    n |= n >>> 8;
    n |= n >>> 16;
    return (n < 0) ? 1 : (n >= MAXIMUM_CAPACITY) ? MAXIMUM_CAPACITY : n + 1;
}
```

#### 8. 链表转红黑树

从 JDK 1.8 开始，一个桶存储的链表长度大于等于 8 时会将链表转换为红黑树。

#### 9. 与 Hashtable 的比较

- Hashtable 使用 synchronized 来进行同步。
- HashMap 可以插入键为 null 的 Entry。
- HashMap 的迭代器是 fail-fast 迭代器。
- HashMap 不能保证随着时间的推移 Map 中的元素次序是不变的。


### 继承关系

![](image/2022-12-15-19-39-03.png)

* HashMap不能包含重复的键。
* HashMap允许多个null值，但只允许一个null键。
* HashMap是一个unordered collection 。 它不保证元素的任何特定顺序。
* HashMap not thread-safe 。 您必须显式同步对HashMap的并发修改。 或者，您可以使用Collections.synchronizedMap(hashMap)来获取HashMap的同步版本。
* 只能使用关联的键来检索值。
* HashMap仅存储对象引用。 因此，必须将原语与其对应的包装器类一起使用。 如int将存储为Integer 。


### 主要方法

```java
void clear() ：从HashMap中删除所有键-值对。
Object clone() ：返回指定HashMap的浅表副本。
boolean containsKey(Object key) ：根据是否在地图中找到指定的键，返回true或false 。
boolean containsValue(Object Value) ：类似于containsKey（）方法，它查找指定的值而不是键。
Object get(Object key) ：返回HashMap中指定键的值。
boolean isEmpty() ：检查地图是否为空。
Set keySet() ：返回存储在HashMap中的所有密钥的Set 。
Object put（Key k，Value v） ：将键值对插入HashMap中。
int size() ：返回地图的大小，该大小等于存储在HashMap中的键值对的数量。
Collection values() ：返回地图中所有值的集合。
Value remove(Object key) ：删除指定键的键值对。
void putAll(Map m) ：将地图的所有元素复制到另一个指定的地图。
```



合并两个hashmap
* 使用HashMap.putAll(HashMap)方法，即可将所有映射从第二张地图复制到第一张地图。hashmap不允许重复的键 。 因此，当我们以这种方式合并map时，对于map1的重复键，其值会被map2相同键的值覆盖。

```java
//map 1
HashMap<Integer, String> map1 = new HashMap<>();
 
map1.put(1, "A");
map1.put(2, "B");
map1.put(3, "C");
map1.put(5, "E");
 
//map 2
HashMap<Integer, String> map2 = new HashMap<>();
 
map2.put(1, "G");   //It will replace the value 'A'
map2.put(2, "B");
map2.put(3, "C");
map2.put(4, "D");   //A new pair to be added
 
//Merge maps
map1.putAll(map2);
 
System.out.println(map1);
```
* merge()函数如果我们要处理在地图中存在重复键的情况，并且我们不想丢失任何地图和任何键的数据。HashMap.merge()函数3个参数。 键，值，并使用用户提供的BiFunction合并重复键的值。跟put一样，实现了重复key的处理。

```java
Merge HashMaps Example
//map 1
HashMap<Integer, String> map1 = new HashMap<>();
 
map1.put(1, "A");
map1.put(2, "B");
map1.put(3, "C");
map1.put(5, "E");
 
//map 2
HashMap<Integer, String> map2 = new HashMap<>();
 
map2.put(1, "G");   //It will replace the value 'A'
map2.put(2, "B");
map2.put(3, "C");
map2.put(4, "D");   //A new pair to be added
 
//Merge maps
map2.forEach(
    (key, value) -> map1.merge( key, value, (v1, v2) -> v1.equalsIgnoreCase(v2) ? v1 : v1 + "," + v2)
);
 
System.out.println(map1);
```

### 遍历方法

通过不同的set遍历呗。包括EntrySet遍历、keyset遍历

```java
1)在每个循环中使用enrtySet（）
for (Map.Entry<String,Integer> entry : testMap.entrySet()) {
    entry.getKey();
    entry.getValue();
}
2）在每个循环中使用keySet（）
for (String key : testMap.keySet()) {
    testMap.get(key);
}
3）使用enrtySet（）和迭代器
Iterator<Map.Entry<String,Integer>> itr1 = testMap.entrySet().iterator();
while(itr1.hasNext())
{
    Map.Entry<String,Integer> entry = itr1.next();
    entry.getKey();
    entry.getValue();
}
4）使用keySet（）和迭代器
Iterator itr2 = testMap.keySet().iterator();
while(itr2.hasNext())
{
    String key = itr2.next();
    testMap.get(key);
}
```

## 2 LinkedHashMap

### 底层原理

LinkedHashMap 可以看作是 `HashMap` 和 `LinkedList` 的结合：它在 HashMap 的基础上添加了一条双向链表，`默认`存储各个元素的插入顺序，但由于这条双向链表，使得 LinkedHashMap 可以实现 `LRU`缓存淘汰策略，因为我们可以设置这条双向链表按照`元素的访问次序`进行排序

![](image/2022-12-15-21-12-52.png)

LinkedHashMap 是 HashMap 的子类，所以它具备 HashMap 的所有特点，其次，它在 HashMap 的基础上维护了一条`双向链表`，该链表存储了**所有元素**，`默认`元素的顺序与插入顺序**一致**。若`accessOrder`属性为`true`，则遍历顺序按元素的访问次序进行排序。

```java
// 头节点
transient LinkedHashMap.Entry<K, V> head;
// 尾结点
transient LinkedHashMap.Entry<K, V> tail;
```

利用 LinkedHashMap  可以实现 `LRU` 缓存淘汰策略，因为它提供了一个方法：

```java
protected boolean removeEldestEntry(java.util.Map.Entry<K, V> eldest) {
    return false;
}
```

该方法可以移除`最靠近链表头部`的一个节点，而在`get()`方法中可以看到下面这段代码，其作用是挪动结点的位置：

```java
if (this.accessOrder) {
    this.afterNodeAccess(e);
}
```

只要调用了`get()`且`accessOrder = true`，则会将该节点更新到链表`尾部`，具体的逻辑在`afterNodeAccess()`中，感兴趣的可翻看源码，篇幅原因这里不再展开。

现在如果要实现一个`LRU`缓存策略，则需要做两件事情：

- 指定`accessOrder = true`可以设定链表按照访问顺序排列，通过提供的构造器可以设定`accessOrder`

```java
public LinkedHashMap(int initialCapacity, float loadFactor, boolean accessOrder) {
    super(initialCapacity, loadFactor);
    this.accessOrder = accessOrder;
}
```

- 重写`removeEldestEntry()`方法，内部定义逻辑，通常是判断`容量`是否达到上限，若是则执行淘汰。

这里就要贴出一道大厂面试必考题目：[146. LRU缓存机制](https://leetcode-cn.com/problems/lru-cache/)，只要跟着我的步骤，就能顺利完成这道大厂题了。

关于 LinkedHashMap 主要介绍两点：

1. 它底层维护了一条`双向链表`，因为继承了 HashMap，所以它也不是线程安全的
2. LinkedHashMap 可实现`LRU`缓存淘汰策略，其原理是通过设置`accessOrder`为`true`并重写`removeEldestEntry`方法定义淘汰元素时需满足的条件


#### 存储结构

继承自 HashMap，因此具有和 HashMap 一样的快速查找特性。

```java
public class LinkedHashMap<K,V> extends HashMap<K,V> implements Map<K,V>
```

内部维护了一个双向链表，用来维护插入顺序或者 LRU 顺序。

```java
/**
 * The head (eldest) of the doubly linked list.
 */
transient LinkedHashMap.Entry<K,V> head;

/**
 * The tail (youngest) of the doubly linked list.
 */
transient LinkedHashMap.Entry<K,V> tail;
```

accessOrder 决定了顺序，默认为 false，此时维护的是插入顺序。

```java
final boolean accessOrder;
```

LinkedHashMap 最重要的是以下用于维护顺序的函数，它们会在 put、get 等方法中调用。

```java
void afterNodeAccess(Node<K,V> p) { }
void afterNodeInsertion(boolean evict) { }
```

#### afterNodeAccess()

当一个节点被访问时，如果 accessOrder 为 true，则会将该节点移到链表尾部。也就是说指定为 LRU 顺序之后，在每次访问一个节点时，会将这个节点移到链表尾部，保证链表尾部是最近访问的节点，那么链表首部就是最近最久未使用的节点。

```java
void afterNodeAccess(Node<K,V> e) { // move node to last
    LinkedHashMap.Entry<K,V> last;
    if (accessOrder && (last = tail) != e) {
        LinkedHashMap.Entry<K,V> p =
            (LinkedHashMap.Entry<K,V>)e, b = p.before, a = p.after;
        p.after = null;
        if (b == null)
            head = a;
        else
            b.after = a;
        if (a != null)
            a.before = b;
        else
            last = b;
        if (last == null)
            head = p;
        else {
            p.before = last;
            last.after = p;
        }
        tail = p;
        ++modCount;
    }
}
```

#### afterNodeInsertion()

在 put 等操作之后执行，当 removeEldestEntry() 方法返回 true 时会移除最晚的节点，也就是链表首部节点 first。

evict 只有在构建 Map 的时候才为 false，在这里为 true。

```java
void afterNodeInsertion(boolean evict) { // possibly remove eldest
    LinkedHashMap.Entry<K,V> first;
    if (evict && (first = head) != null && removeEldestEntry(first)) {
        K key = first.key;
        removeNode(hash(key), key, null, false, true);
    }
}
```

removeEldestEntry() 默认为 false，如果需要让它为 true，需要继承 LinkedHashMap 并且覆盖这个方法的实现，这在实现 LRU 的缓存中特别有用，通过移除最近最久未使用的节点，从而保证缓存空间足够，并且缓存的数据都是热点数据。

```java
protected boolean removeEldestEntry(Map.Entry<K,V> eldest) {
    return false;
}
```

#### LRU 缓存

以下是使用 LinkedHashMap 实现的一个 LRU 缓存：

- 设定最大缓存空间 MAX_ENTRIES  为 3；
- 使用 LinkedHashMap 的构造函数将 accessOrder 设置为 true，开启 LRU 顺序；
- 覆盖 removeEldestEntry() 方法实现，在节点多于 MAX_ENTRIES 就会将最近最久未使用的数据移除。

```java
class LRUCache<K, V> extends LinkedHashMap<K, V> {
    private static final int MAX_ENTRIES = 3;

    protected boolean removeEldestEntry(Map.Entry eldest) {
        return size() > MAX_ENTRIES;
    }

    LRUCache() {
        super(MAX_ENTRIES, 0.75f, true);
    }
}
```

```java
public static void main(String[] args) {
    LRUCache<Integer, String> cache = new LRUCache<>();
    cache.put(1, "a");
    cache.put(2, "b");
    cache.put(3, "c");
    cache.get(1);
    cache.put(4, "d");
    System.out.println(cache.keySet());
}
```

```html
[3, 1, 4]
```



## 3 TreeMap

### 底层原理
TreeMap 是 `SortedMap` 的子类，所以它具有**排序**功能。它是基于`红黑树`数据结构实现的，每一个键值对`<key, value>`都是一个结点，默认情况下按照`key`自然排序，另一种是可以通过传入定制的`Comparator`进行自定义规则排序。

```java
// 按照 key 自然排序，Integer 的自然排序是升序
TreeMap<Integer, Object> naturalSort = new TreeMap<>();
// 定制排序，按照 key 降序排序
TreeMap<Integer, Object> customSort = new TreeMap<>((o1, o2) -> Integer.compare(o2, o1));
```

TreeMap 底层使用了数组+红黑树实现，所以里面的存储结构可以理解成下面这幅图哦。

![image-20200730180101883.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1596103385086-d684f26e-dabd-44b7-bab8-151af172496a.png)

图中红黑树的每一个节点都是一个`Entry`，在这里为了图片的简洁性，就不标明 key 和 value 了，注意这些元素都是已经按照`key`排好序了，整个数据结构都是保持着`有序` 的状态！

关于`自然`排序与`定制`排序：

- 自然排序：要求`key`必须实现`Comparable`接口。

由于`Integer`类实现了 Comparable 接口，按照自然排序规则是按照`key`从小到大排序。

```java
TreeMap<Integer, String> treeMap = new TreeMap<>();
treeMap.put(2, "TWO");
treeMap.put(1, "ONE");
System.out.print(treeMap);
// {1=ONE, 2=TWO}
```

- 定制排序：在初始化 TreeMap 时传入新的`Comparator`，**不**要求`key`实现 Comparable 接口

```java
TreeMap<Integer, String> treeMap = new TreeMap<>((o1, o2) -> Integer.compare(o2, o1));
treeMap.put(1, "ONE");
treeMap.put(2, "TWO");
treeMap.put(4, "FOUR");
treeMap.put(3, "THREE");
System.out.println(treeMap);
// {4=FOUR, 3=THREE, 2=TWO, 1=ONE}
```

通过传入新的`Comparator`比较器，可以覆盖默认的排序规则，上面的代码按照`key`降序排序，在实际应用中还可以按照其它规则自定义排序。

`compare()`方法的返回值有三种，分别是：`0`，`-1`，`+1`

（1）如果返回`0`，代表两个元素相等，不需要调换顺序

（2）如果返回`+1`，代表前面的元素需要与后面的元素调换位置

（3）如果返回`-1`，代表前面的元素不需要与后面的元素调换位置

而何时返回`+1`和`-1`，则由我们自己去定义，JDK默认是按照**自然排序**，而我们可以根据`key`的不同去定义降序还是升序排序。

关于 TreeMap 主要介绍了两点：

1. 它底层是由`红黑树`这种数据结构实现的，所以操作的时间复杂度恒为`O(logN)`
2. TreeMap 可以对`key`进行自然排序或者自定义排序，自定义排序时需要传入`Comparator`，而自然排序要求`key`实现了`Comparable`接口
3. TreeMap 不是线程安全的。它不synchronized 。 使用Collections.synchronizedSortedMap(new TreeMap())在并发环境中工作。
4. 它不能具有null键，但可以具有多个null值。
5. 它以排序顺序（自然顺序）或地图创建时提供的Comparator来存储键。
6. 它为containsKey ， get ， put和remove操作提供了保证的log(n)时间成本。

### 主要方法

```java
void clear():从地图中删除所有键/值对。
void size():返回此映射中存在的键值对的数量。
void isEmpty():如果此映射不包含键值映射，则返回true。
boolean containsKey(Object key):如果地图中存在指定的键，则返回'true' 。
boolean containsValue(Object key):如果将指定值映射到映射中的至少一个键，则返回'true' 。
Object get(Object key):检索由指定key映射的值；如果此映射不包含key映射关系，则返回null。
Object remove(Object key):如果存在，则从映射中删除指定键的键值对。
Comparator comparator():它返回用于对该映射中的键进行排序的比较器；如果此映射使用其键的自然排序，则返回null。
Object firstKey():返回树图中当前的第一个（最小）键。
Object lastKey():返回树图中当前的最后一个（最大）键。
Object ceilingKey(Object key):返回大于或等于给定键的最小键；如果没有这样的键，则返回null。
Object higherKey(Object key):返回严格大于指定键的最小键。
NavigableMap descendingMap():它返回此地图中包含的映射的reverse order view 。
```

## 4 WeakHashMap 

WeakHashMap 日常开发中比较少见，它是基于普通的`Map`实现的，而里面`Entry`中的键在每一次的`垃圾回收`都会被清除掉，所以非常适合用于**短暂访问、仅访问一次**的元素，缓存在`WeakHashMap`中，并尽早地把它回收掉。

当`Entry`被`GC`时，WeakHashMap 是如何感知到某个元素被回收的呢？

在 WeakHashMap 内部维护了一个引用队列`queue`

```java
private final ReferenceQueue<Object> queue = new ReferenceQueue<>();
```

这个 queue 里包含了所有被`GC`掉的键，当JVM开启`GC`后，如果回收掉 WeakHashMap 中的 key，会将 key 放入queue 中，在`expungeStaleEntries()`中遍历 queue，把 queue 中的所有`key`拿出来，并在 WeakHashMap 中删除掉，以达到**同步**。

```java
private void expungeStaleEntries() {
    for (Object x; (x = queue.poll()) != null; ) {
        synchronized (queue) {
            // 去 WeakHashMap 中删除该键值对
        }
    }
}
```

再者，需要注意 WeakHashMap 底层存储的元素的数据结构是`数组 + 链表`，**没有红黑树**哦，可以换一个角度想，如果还有红黑树，那干脆直接继承 HashMap ，然后再扩展就完事了嘛，然而它并没有这样做：

```java
public class WeakHashMap<K, V> extends AbstractMap<K, V> implements Map<K, V> {
    
}
```

所以，WeakHashMap 的数据结构图我也为你准备好啦。

![image.png](https://cdn.nlark.com/yuque/0/2020/png/1694029/1596106079292-a74fb47e-bb54-47e2-81ac-1254428e73b7.png)

图中被虚线标识的元素将会在下一次访问 WeakHashMap 时被删除掉，WeakHashMap 内部会做好一系列的调整工作，所以记住队列的作用就是标志那些已经被`GC`回收掉的元素。

关于 WeakHashMap 需要注意两点：

1. 它的键是一种**弱键**，放入 WeakHashMap 时，随时会被回收掉，所以不能确保某次访问元素一定存在
2. 它依赖普通的`Map`进行实现，是一个非线程安全的集合
3. WeakHashMap 通常作为**缓存**使用，适合存储那些**只需访问一次**、或**只需保存短暂时间**的键值对


### 存储结构

WeakHashMap 的 Entry 继承自 WeakReference，被 WeakReference 关联的对象在下一次垃圾回收时会被回收。

WeakHashMap 主要用来实现缓存，通过使用 WeakHashMap 来引用缓存对象，由 JVM 对这部分缓存进行回收。

```java
private static class Entry<K,V> extends WeakReference<Object> implements Map.Entry<K,V>
```

### ConcurrentCache

Tomcat 中的 ConcurrentCache 使用了 WeakHashMap 来实现缓存功能。

ConcurrentCache 采取的是分代缓存：

- 经常使用的对象放入 eden 中，eden 使用 ConcurrentHashMap 实现，不用担心会被回收（伊甸园）；
- 不常用的对象放入 longterm，longterm 使用 WeakHashMap 实现，这些老对象会被垃圾收集器回收。
- 当调用  get() 方法时，会先从 eden 区获取，如果没有找到的话再到 longterm 获取，当从 longterm 获取到就把对象放入 eden 中，从而保证经常被访问的节点不容易被回收。
- 当调用 put() 方法时，如果 eden 的大小超过了 size，那么就将 eden 中的所有对象都放入 longterm 中，利用虚拟机回收掉一部分不经常使用的对象。

```java
public final class ConcurrentCache<K, V> {

    private final int size;

    private final Map<K, V> eden;

    private final Map<K, V> longterm;

    public ConcurrentCache(int size) {
        this.size = size;
        this.eden = new ConcurrentHashMap<>(size);
        this.longterm = new WeakHashMap<>(size);
    }

    public V get(K k) {
        V v = this.eden.get(k);
        if (v == null) {
            v = this.longterm.get(k);
            if (v != null)
                this.eden.put(k, v);
        }
        return v;
    }

    public void put(K k, V v) {
        if (this.eden.size() >= size) {
            this.longterm.putAll(this.eden);
            this.eden.clear();
        }
        this.eden.put(k, v);
    }
}
```


## 5 Hashtable :warning: 已废弃
### 底层原理
Hashtable 底层的存储结构是`数组 + 链表`，而它是一个**线程安全**的集合，但是因为这个线程安全，它就被淘汰掉了。

下面是Hashtable存储元素时的数据结构图，它只会存在数组+链表，当链表过长时，查询的效率过低，而且会长时间**锁住** Hashtable。

![](image/2022-12-15-20-19-36.png)

> 本质上就是 WeakHashMap 的底层存储结构了。你千万别问为什么 WeakHashMap 不继承 Hashtable 哦，Hashtable 的`性能`在并发环境下非常差，在非并发环境下可以用`HashMap`更优。

HashTable 本质上是 HashMap 的前辈，它被淘汰的原因也主要因为两个字：**性能**

HashTable 是一个 **线程安全** 的 Map，它所有的方法都被加上了 **synchronized** 关键字，也是因为这个关键字，它注定成为了时代的弃儿。

HashTable 底层采用 **数组+链表** 存储键值对，由于被弃用，后人也没有对它进行任何改进

HashTable 默认长度为 `11`，负载因子为 `0.75F`，即元素个数达到数组长度的 75% 时，会进行一次扩容，每次扩容为原来数组长度的 `2` 倍

HashTable 所有的操作都是线程安全的。

### 方法
跟hashtable一样
