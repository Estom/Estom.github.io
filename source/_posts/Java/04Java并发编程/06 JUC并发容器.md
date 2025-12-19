---
title: "06 JUC并发容器"
date: 1766125929
updated: 1766125929
tags: []
categories:
  - "Java"
---

# 2 J.U.C -并发容器

并发集合是指使用了最新并发能力的集合，在JUC包下。而同步集合指之前用同步锁实现的集合。

其对应的基础集合类的接口并没有发生太大变化，主要是针对并发场景进行优化，使用各种方式保证并发集合的安全性。

## 1 CopyOnWrite

### CopyOnWriteArrayList

CopyOnWriteArrayList在写的时候会复制一个副本，对副本写，写完用副本替换原值，读的时候不需要同步，适用于写少读多的场合。


CopyOnWriteArraySet基于CopyOnWriteArrayList来实现的，只是在不允许存在重复的对象这个特性上遍历处理了一下。

#### 读写分离

写操作在一个复制的数组上进行，读操作还是在原始数组中进行，读写分离，互不影响。

写操作需要加锁，防止并发写入时导致写入数据丢失。

写操作结束之后需要把原始数组指向新的复制数组。

```java
public boolean add(E e) {
    final ReentrantLock lock = this.lock;
    lock.lock();
    try {
        Object[] elements = getArray();
        int len = elements.length;
        Object[] newElements = Arrays.copyOf(elements, len + 1);
        newElements[len] = e;
        setArray(newElements);
        return true;
    } finally {
        lock.unlock();
    }
}

final void setArray(Object[] a) {
    array = a;
}
```

```java
@SuppressWarnings("unchecked")
private E get(Object[] a, int index) {
    return (E) a[index];
}
```

#### 适用场景

CopyOnWriteArrayList 在写操作的同时允许读操作，大大提高了读操作的性能，因此很适合读多写少的应用场景。

但是 CopyOnWriteArrayList 有其缺陷：

- 内存占用：在写操作时需要复制一个新的数组，使得内存占用为原来的两倍左右；
- 数据不一致：读操作不能读取实时性的数据，因为部分写操作的数据还未同步到读数组中。

所以 CopyOnWriteArrayList 不适合内存敏感以及对实时性要求很高的场景。


> 用来替代vector，提供现成安全的list
#### 底层原理

Java CopyOnWriteArrayList是ArrayList的thread-safe变体，其中所有可变操作（添加，设置等）都通过对基础array进行全新复制来实现。

* CopyOnWriteArrayList类实现List和RandomAccess接口，因此提供ArrayList类中可用的所有功能。
* 使用CopyOnWriteArrayList进行更新操作的成本很高，因为每个突变都会创建基础数组的克隆副本，并为其添加/更新元素。
* 它是ArrayList的线程安全版本。 每个访问列表的线程在初始化此列表的迭代器时都会看到自己创建的后备阵列快照版本。
* 因为它在创建迭代器时获取基础数组的快照，所以它不会抛出ConcurrentModificationException 。
* 不支持对迭代器的删除操作（删除，设置和添加）。 这些方法抛出UnsupportedOperationException 。
* CopyOnWriteArrayList是synchronized List的并发替代，当迭代的次数超过突变次数时，CopyOnWriteArrayList可以提供更好的并发性。
* 它允许重复的元素和异构对象（使用泛型来获取编译时错误）。因为它每次创建迭代器时都会创建一个新的数组副本，所以performance is slower比ArrayList performance is slower 。


#### 实例

```java
CopyOnWriteArrayList<Integer> list = new CopyOnWriteArrayList<>(new Integer[] {1,2,3});
 
System.out.println(list);   //[1, 2, 3]
 
//Get iterator 1
Iterator<Integer> itr1 = list.iterator();
 
//Add one element and verify list is updated
list.add(4);
 
System.out.println(list);   //[1, 2, 3, 4]
 
//Get iterator 2
Iterator<Integer> itr2 = list.iterator();
 
System.out.println("====Verify Iterator 1 content====");
 
itr1.forEachRemaining(System.out :: println);   //1,2,3
 
System.out.println("====Verify Iterator 2 content====");
 
itr2.forEachRemaining(System.out :: println);   //1,2,3,4
```

#### 主要方法

```java
CopyOnWriteArrayList() ：创建一个空列表。
CopyOnWriteArrayList(Collection c) ：创建一个列表，该列表包含指定集合的​​元素，并按集合的迭代器返回它们的顺序。
CopyOnWriteArrayList(object[] array) ：创建一个保存给定数组副本的列表。
boolean addIfAbsent(object o) ：如果不存在则追加元素。
int addAllAbsent(Collection c) ：以指定集合的​​迭代器返回的顺序，将指定集合中尚未包含在此列表中的所有元素追加到此列表的末尾。
```



### CopyOnWriteArraySet

#### 底层原理
HashSet的thread-safe变体，它对所有操作都使用基础CopyOnWriteArrayList 

与CopyOnWriteArrayList相似，它的immutable snapshot样式iterator方法在创建iterator使用对数组状态（在后备列表内）的引用。 这在遍历操作远远超过集合更新操作且我们不想同步遍历并且在更新集合时仍希望线程安全的用例中很有用。

* 作为正常设置的数据结构，它不允许重复。
* CopyOnWriteArraySet类实现Serializable接口并扩展AbstractSet类。
* 使用CopyOnWriteArraySet进行更新操作成本很高，因为每个突变都会创建基础数组的克隆副本并向其添加/更新元素。
* 它是HashSet的线程安全版本。 每个访问该集合的线程在初始化此集合的迭代器时都会看到自己创建的后备阵列快照版本。
* 因为它在创建迭代器时获取基础数组的快照，所以它不会抛出ConcurrentModificationException 。不支持迭代器上的变异操作。 这些方法抛出UnsupportedOperationException 。
* CopyOnWriteArraySet是synchronized Set的并发替代，当迭代的次数超过突变次数时，CopyOnWriteArraySet提供更好的并发性。
* 它允许重复的元素和异构对象（使用泛型来获取编译时错误）。
* 由于每次创建迭代器时都会创建基础数组的新副本，因此performance is slower HashSet 

#### 主要方法

```java
CopyOnWriteArraySet() ：创建一个空集。
CopyOnWriteArraySet(Collection c) ：创建一个包含指定集合元素的集合，其顺序由集合的迭代器返回。
boolean add(object o) ：将指定的元素添加到此集合（如果尚不存在）。
boolean addAll(collection c) ：将指定集合中的所有元素（如果尚不存在boolean addAll(collection c)添加到此集合中。
void clear() ：从此集合中删除所有元素。
boolean contains(Object o) ：如果此集合包含指定的元素，则返回true。
boolean isEmpty() ：如果此集合不包含任何元素，则返回true。
Iterator iterator() ：以添加这些元素的顺序在此集合中包含的元素上返回一个迭代器。
boolean remove(Object o) ：从指定的集合中删除指定的元素（如果存在）。
int size() ：返回此集合中的元素数
```


#### 实例

```java
CopyOnWriteArraySet<Integer> set = new CopyOnWriteArraySet<>(Arrays.asList(1,2,3));
 
System.out.println(set);    //[1, 2, 3]
 
//Get iterator 1
Iterator<Integer> itr1 = set.iterator();
 
//Add one element and verify set is updated
set.add(4);
System.out.println(set);    //[1, 2, 3, 4]
 
//Get iterator 2
Iterator<Integer> itr2 = set.iterator();
 
System.out.println("====Verify Iterator 1 content====");
 
itr1.forEachRemaining(System.out :: println);   //1,2,3
 
System.out.println("====Verify Iterator 2 content====");
 
itr2.forEachRemaining(System.out :: println);   //1,2,3,4
```

## 2 BlockingQueue

在并发队列上JDK提供了两套实现，
* 一个是以ConcurrentLinkedQueue为代表的高性能队列
* 一个是以BlockingQueue接口为代表的阻塞队列。

ConcurrentLinkedQueue适用于高并发场景下的队列，通过无锁的方式实现，通常ConcurrentLinkedQueue的性能要优于BlockingQueue。BlockingQueue的典型应用场景是生产者-消费者模式中，如果生产快于消费，生产队列装满时会阻塞，等待消费。



java.util.concurrent.BlockingQueue 接口有以下阻塞队列的实现：

-   **FIFO 队列**  ：LinkedBlockingQueue、LinkedBlockingDeque、ArrayBlockingQueue（固定长度）
-   **优先级队列**  ：PriorityBlockingQueue
-   TransferQueue
-   DelayQueue

提供了阻塞的 take() 和 put() 方法：如果队列为空 take() 将阻塞，直到队列中有内容；如果队列为满 put() 将阻塞，直到队列有空闲位置。

**使用 BlockingQueue 实现生产者消费者问题**  

```java
public class ProducerConsumer {

    private static BlockingQueue<String> queue = new ArrayBlockingQueue<>(5);

    private static class Producer extends Thread {
        @Override
        public void run() {
            try {
                queue.put("product");
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            System.out.print("produce..");
        }
    }

    private static class Consumer extends Thread {

        @Override
        public void run() {
            try {
                String product = queue.take();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            System.out.print("consume..");
        }
    }
}
```

```java
public static void main(String[] args) {
    for (int i = 0; i < 2; i++) {
        Producer producer = new Producer();
        producer.start();
    }
    for (int i = 0; i < 5; i++) {
        Consumer consumer = new Consumer();
        consumer.start();
    }
    for (int i = 0; i < 3; i++) {
        Producer producer = new Producer();
        producer.start();
    }
}
```

```html
produce..produce..consume..consume..produce..consume..produce..consume..produce..consume..
```



### PriorityBlockingQueue

#### 底层原理
Java PriorityBlockingQueue类是concurrent阻塞队列数据结构的实现，其中根据对象的priority对其进行处理。 名称的“阻塞”部分已添加，表示线程将阻塞等待，直到队列上有可用的项目为止 。

在priority blocking queue ，添加的对象根据其优先级进行排序。 默认情况下，优先级由对象的自然顺序决定。 队列构建时提供的Comparator器可以覆盖默认优先级。
* PriorityBlockingQueue是一个无界队列，并且会动态增长。 默认初始容量为'11' ，可以在适当的构造函数中使用initialCapacity参数覆盖此初始容量。
* 它**提供了阻塞检索操作**。
* 它不允许使用NULL对象。
* 添加到PriorityBlockingQueue的对象必须具有可比性，否则它将引发ClassCastException 。
* 默认情况下，优先级队列的对象以自然顺序排序 。
* 比较器可用于队列中对象的自定义排序。
* 优先级队列的head是基于自然排序或基于比较器排序的least元素。 当我们轮询队列时，它从队列中返回头对象。
* 如果存在多个具有相同优先级的对象，则它可以随机轮询其中的任何一个。
* PriorityBlockingQueue是thread safe 。

#### 主要方法

```java
boolean add(object) ：将指定的元素插入此优先级队列。
boolean offer(object) ：将指定的元素插入此优先级队列。
boolean remove(object) ：从此队列中移除指定元素的单个实例（如果存在）。
Object poll() ：检索并删除此队列的头部，并在必要时等待指定的等待时间，以使元素可用。
Object poll(timeout, timeUnit) ：检索并删除此队列的头部，如果有必要，直到指定的等待时间，元素才可用。
Object take() ：检索并删除此队列的头部，如有必要，请等待直到元素可用。
void put(Object o) ：将指定的元素插入此优先级队列。
void clear() ：从此优先级队列中删除所有元素。
Comparator comparator() ：返回用于对此队列中的元素进行排序的Comparator comparator()如果此队列是根据其元素的自然顺序排序的，则返回null。
boolean contains(Object o) ：如果此队列包含指定的元素，则返回true。
Iterator iterator() ：返回对该队列中的元素进行迭代的迭代器。
int size() ：返回此队列中的元素数。
int drainTo(Collection c) ：从此队列中删除所有可用元素，并将它们添加到给定的collection中。
intrainToTo（Collection c，int maxElements） ：从此队列中最多移除给定数量的可用元素，并将它们添加到给定的collection中。
int remainingCapacity() Integer.MAX_VALUE int remainingCapacity() ：总是返回Integer.MAX_VALUE因为PriorityBlockingQueue不受容量限制。
Object[] toArray() ：返回一个包含此队列中所有元素的数组。
```
#### 实例
```java
import java.util.concurrent.PriorityBlockingQueue;
import java.util.concurrent.TimeUnit;
 
public class PriorityQueueExample 
{
    public static void main(String[] args) throws InterruptedException 
    {
        PriorityBlockingQueue<Integer> priorityBlockingQueue = new PriorityBlockingQueue<>();
         
        new Thread(() -> 
        {
          System.out.println("Waiting to poll ...");
          
          try
          {
              while(true) 
              {
                  Integer poll = priorityBlockingQueue.take();
                  System.out.println("Polled : " + poll);
 
                  Thread.sleep(TimeUnit.SECONDS.toMillis(1));
              }
               
          } catch (InterruptedException e) {
              e.printStackTrace();
          }
           
        }).start();
          
        Thread.sleep(TimeUnit.SECONDS.toMillis(2));
        priorityBlockingQueue.add(1);
         
        Thread.sleep(TimeUnit.SECONDS.toMillis(2));
        priorityBlockingQueue.add(2);
         
        Thread.sleep(TimeUnit.SECONDS.toMillis(2));
        priorityBlockingQueue.add(3);
    }
}
```

### ArrayBlockingQueue

#### 底层原理

ArrayBlockingQueue类是由数组支持的Java concurrent和bounded阻塞队列实现。 它对元素FIFO（先进先出）进行排序。

ArrayBlockingQueue的head是一直在队列中最长时间的那个元素。 ArrayBlockingQueue的tail是最短时间进入队列的元素。 新元素插入到队列的尾部 ，并且队列检索操作在队列的开头获取元素 。

* ArrayBlockingQueue是由数组支持的固定大小的有界队列。
* 它对元素FIFO（先进先出）进行排序。
* 元素插入到尾部，并从队列的开头检索。
* 创建后，队列的容量无法更改。
* 它提供阻塞的插入和检索操作 。
* 它不允许使用NULL对象。
* ArrayBlockingQueue是thread safe 。
* 方法iterator()提供的Iterator按从第一个（头）到最后一个（尾部）的顺序遍历元素。
* ArrayBlockingQueue支持可选的fairness policy用于订购等待的生产者线程和使用者线程。 将fairness设置为true ，队列按FIFO顺序授予线程访问权限。




#### 生产消费者实例
使用阻塞插入和检索从ArrayBlockingQueue中放入和取出元素的Java示例。

* 当队列已满时，生产者线程将等待。 一旦从队列中取出一个元素，它就会将该元素添加到队列中。
* 如果队列为空，使用者线程将等待。 队列中只有一个元素时，它将取出该元素。
```java
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
 
public class ArrayBlockingQueueExample 
{
    public static void main(String[] args) throws InterruptedException 
    {
        ArrayBlockingQueue<Integer> priorityBlockingQueue = new ArrayBlockingQueue<>(5);
 
        //Producer thread
        new Thread(() -> 
        {
            int i = 0;
            try
            {
                while (true) 
                {
                    priorityBlockingQueue.put(++i);
                    System.out.println("Added : " + i);
                     
                    Thread.sleep(TimeUnit.SECONDS.toMillis(1));
                }
 
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
 
        }).start();
 
        //Consumer thread
        new Thread(() -> 
        {
            try
            {
                while (true) 
                {
                    Integer poll = priorityBlockingQueue.take();
                    System.out.println("Polled : " + poll);
                     
                    Thread.sleep(TimeUnit.SECONDS.toMillis(2));
                }
 
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
 
        }).start();
    }
}
```

#### 主要方法

```java
ArrayBlockingQueue(int capacity) ：构造具有给定（固定）容量和默认访问策略的空队列。
ArrayBlockingQueue（int capacity，boolean fair） ：构造具有给定（固定）容量和指定访问策略的空队列。 如果公允值为true ，则按FIFO顺序处理在插入或移除时阻塞的线程的队列访问； 如果为false，则未指定访问顺序。
ArrayBlockingQueue（int capacity，boolean fair，Collection c） ：构造一个队列，该队列具有给定（固定）的容量，指定的访问策略，并最初包含给定集合的元素，并以集合迭代器的遍历顺序添加。
void put(Object o) ：将指定的元素插入此队列的尾部，如果队列已满，则等待空间变为可用。
boolean add(object) : Inserts the specified element at the tail of this queue if it is possible to do so immediately without exceeding the queue’s capacity, returning true upon success and throwing an IllegalStateException if this queue is full.
boolean offer(object) ：如果可以在不超出队列容量的情况下立即执行此操作，则在此队列的尾部插入指定的元素，如果成功，则返回true，如果此队列已满，则抛出IllegalStateException。
boolean remove(object) ：从此队列中移除指定元素的单个实例（如果存在）。
Object peek() ：检索但不删除此队列的头部；如果此队列为空，则返回null。
Object poll() ：检索并删除此队列的头部；如果此队列为空，则返回null。
Object poll(timeout, timeUnit) ：检索并删除此队列的头部，如果有必要，直到指定的等待时间，元素才可用。
Object take() ：检索并删除此队列的头部，如有必要，请等待直到元素可用。
void clear() ：从队列中删除所有元素。
boolean contains(Object o) ：如果此队列包含指定的元素，则返回true。
Iterator iterator() ：以适当的顺序返回对该队列中的元素进行迭代的迭代器。
int size() ：返回此队列中的元素数。
int drainTo(Collection c) ：从此队列中删除所有可用元素，并将它们添加到给定的collection中。
intrainToTo（Collection c，int maxElements） ：从此队列中最多移除给定数量的可用元素，并将它们添加到给定的collection中。
int remainingCapacity() ：返回该队列理想情况下（在没有内存或资源限制的情况下）可以接受而不阻塞的其他元素的数量。
Object[] toArray() ：以适当的顺序返回一个包含此队列中所有元素的数组。
```


### LinkedTransferQueue

#### 底层原理

直接消息队列。也就是说，生产者生产后，必须等待消费者来消费才能继续执行。

Java TransferQueue是并发阻塞队列的实现，生产者可以在其中等待使用者使用消息。 LinkedTransferQueue类是Java中TransferQueue的实现。


* LinkedTransferQueue是链接节点上的unbounded队列。
* 此队列针对任何给定的生产者对元素FIFO（先进先出）进行排序。
* 元素插入到尾部，并从队列的开头检索。
* 它提供阻塞的插入和检索操作 。
* 它不允许使用NULL对象。
* LinkedTransferQueue是thread safe 。
* 由于异步性质，size（）方法不是固定时间操作，因此，如果在遍历期间修改此集合，则可能会报告不正确的结果。
* 不保证批量操作addAll，removeAll，retainAll，containsAll，equals和toArray是原子执行的。 例如，与addAll操作并发操作的迭代器可能仅查看某些添加的元素。



#### 实例
非阻塞实例

```java
LinkedTransferQueue<Integer> linkedTransferQueue = new LinkedTransferQueue<>();
         
linkedTransferQueue.put(1);
 
System.out.println("Added Message = 1");
 
Integer message = linkedTransferQueue.poll();
 
System.out.println("Recieved Message = " + message);
```

阻塞插入实例，用于现成状态同步通信
使用阻塞插入和检索从LinkedTransferQueue放入和取出元素的Java示例。

* 生产者线程将等待，直到有消费者准备从队列中取出项目为止。
* 如果队列为空，使用者线程将等待。 队列中只有一个元素时，它将取出该元素。 只有在消费者接受了消息之后，生产者才可以再发送一条消息。




```java
import java.util.Random;
import java.util.concurrent.LinkedTransferQueue;
import java.util.concurrent.TimeUnit;
 
public class LinkedTransferQueueExample 
{
    public static void main(String[] args) throws InterruptedException 
    {
        LinkedTransferQueue<Integer> linkedTransferQueue = new LinkedTransferQueue<>();
 
        new Thread(() -> 
        {
            Random random = new Random(1);
            try
            {
                while (true) 
                {
                    System.out.println("Producer is waiting to transfer message...");
                     
                    Integer message = random.nextInt();
                    boolean added = linkedTransferQueue.tryTransfer(message);
                    if(added) {
                        System.out.println("Producer added the message - " + message);
                    }
                    Thread.sleep(TimeUnit.SECONDS.toMillis(3));
                }
 
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
 
        }).start();
         
        new Thread(() -> 
        {
            try
            {
                while (true) 
                {
                    System.out.println("Consumer is waiting to take message...");
                     
                    Integer message = linkedTransferQueue.take();
                     
                    System.out.println("Consumer recieved the message - " + message);
                     
                    Thread.sleep(TimeUnit.SECONDS.toMillis(3));
                }
 
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
 
        }).start();
    }
}
```


### 主要方法

```java
LinkedTransferQueue() ：构造一个初始为空的LinkedTransferQueue。
LinkedTransferQueue(Collection c) ：构造一个LinkedTransferQueue，最初包含给定集合的元素，并以该集合的迭代器的遍历顺序添加。
Object take() ：检索并删除此队列的头部，如有必要，请等待直到元素可用。
void transfer(Object o) ：将元素传输给使用者，如有必要，请等待。
boolean tryTransfer(Object o) ：如果可能，立即将元素传输到等待的使用者。
boolean tryTransfer（Object o，long timeout，TimeUnit unit） ：如果有可能，则在超时之前将元素传输给使用者。
int getWaitingConsumerCount() ：返回等待通过BlockingQueue.take（）或定时轮询接收元素的使用者数量的估计值。
boolean hasWaitingConsumer() ：如果至少有一个使用者正在等待通过BlockingQueue.take（）或定时轮询接收元素，则返回true。
void put(Object o) ：将指定的元素插入此队列的尾部。
boolean add(object) : Inserts the specified element at the tail of this queue.
boolean offer(object) ：将指定的元素插入此队列的尾部。
boolean remove(object) ：从此队列中移除指定元素的单个实例（如果存在）。
Object peek() ：检索但不删除此队列的头部；如果此队列为空，则返回null。
Object poll() ：检索并删除此队列的头部；如果此队列为空，则返回null。
Object poll(timeout, timeUnit) ：检索并删除此队列的头部，如果有必要，直到指定的等待时间，元素才可用。
void clear() ：从队列中删除所有元素。
boolean contains(Object o) ：如果此队列包含指定的元素，则返回true。
Iterator iterator() ：以适当的顺序返回对该队列中的元素进行迭代的迭代器。
int size() ：返回此队列中的元素数。
int drainTo(Collection c) ：从此队列中删除所有可用元素，并将它们添加到给定的collection中。
intrainToTo（Collection c，int maxElements） ：从此队列中最多移除给定数量的可用元素，并将它们添加到给定的collection中。
int remainingCapacity() ：返回该队列理想情况下（在没有内存或资源限制的情况下）可以接受而不阻塞的其他元素的数量。
Object[] toArray() ：以适当的顺序返回一个包含此队列中所有元素的数组。
```



## 3 Concurrent
* ConcurrentLinkedQueue
* ConcurrentLinkedDeque

* ConcurrentHashMap
* ConcurrentHashSet



* ConcurrentSkipListMap
* ConcurrentSkipListSet

ConcurrentHashMap是专用于高并发的Map实现，内部实现进行了锁分离，get操作是无锁的。

java api也提供了一个实现ConcurrentSkipListMap接口的类，ConcurrentSkipListMap接口实现了与ConcurrentNavigableMap接口有相同行为的一个非阻塞式列表。从内部实现机制来讲，它使用了一个Skip List来存放数据。Skip List是基于并发列表的数据结构，效率与二叉树相近。
当插入元素到映射中时，ConcurrentSkipListMap接口类使用键值来排序所有元素。除了提供返回一个具体元素的方法外，这个类也提供获取子映射的方法。

ConcurrentSkipListMap类提供的常用方法：
```java
1.headMap(K toKey)：K是在ConcurrentSkipListMap对象的 泛型参数里用到的键。这个方法返回映射中所有键值小于参数值toKey的子映射。
2.tailMap(K fromKey)：K是在ConcurrentSkipListMap对象的 泛型参数里用到的键。这个方法返回映射中所有键值大于参数值fromKey的子映射。
3.putIfAbsent(K key,V value)：如果映射中不存在键key，那么就将key和value保存到映射中。
4.pollLastEntry()：返回并移除映射中的最后一个Map.Entry对象。
5.replace(K key,V value)：如果映射中已经存在键key，则用参数中的value替换现有的值。
```



### ConcurrentHashMap

#### 底层原理

#### 1. 存储结构

![alt text](image/image.png)
```java
static final class HashEntry<K,V> {
    final int hash;
    final K key;
    volatile V value;
    volatile HashEntry<K,V> next;
}
```

ConcurrentHashMap 和 HashMap 实现上类似，最主要的差别是 ConcurrentHashMap 采用了分段锁（Segment），每个分段锁维护着几个桶（HashEntry），多个线程可以同时访问不同分段锁上的桶，从而使其并发度更高（并发度就是 Segment 的个数）。

Segment 继承自 ReentrantLock。

```java
static final class Segment<K,V> extends ReentrantLock implements Serializable {

    private static final long serialVersionUID = 2249069246763182397L;

    static final int MAX_SCAN_RETRIES =
        Runtime.getRuntime().availableProcessors() > 1 ? 64 : 1;

    transient volatile HashEntry<K,V>[] table;

    transient int count;

    transient int modCount;

    transient int threshold;

    final float loadFactor;
}
```

```java
final Segment<K,V>[] segments;
```

默认的并发级别为 16，也就是说默认创建 16 个 Segment。

```java
static final int DEFAULT_CONCURRENCY_LEVEL = 16;
```

#### 2. size 操作

每个 Segment 维护了一个 count 变量来统计该 Segment 中的键值对个数。

```java
/**
 * The number of elements. Accessed only either within locks
 * or among other volatile reads that maintain visibility.
 */
transient int count;
```

在执行 size 操作时，需要遍历所有 Segment 然后把 count 累计起来。

ConcurrentHashMap 在执行 size 操作时先尝试不加锁，如果连续两次不加锁操作得到的结果一致，那么可以认为这个结果是正确的。

尝试次数使用 RETRIES_BEFORE_LOCK 定义，该值为 2，retries 初始值为 -1，因此尝试次数为 3。

如果尝试的次数超过 3 次，就需要对每个 Segment 加锁。

```java

/**
 * Number of unsynchronized retries in size and containsValue
 * methods before resorting to locking. This is used to avoid
 * unbounded retries if tables undergo continuous modification
 * which would make it impossible to obtain an accurate result.
 */
static final int RETRIES_BEFORE_LOCK = 2;

public int size() {
    // Try a few times to get accurate count. On failure due to
    // continuous async changes in table, resort to locking.
    final Segment<K,V>[] segments = this.segments;
    int size;
    boolean overflow; // true if size overflows 32 bits
    long sum;         // sum of modCounts
    long last = 0L;   // previous sum
    int retries = -1; // first iteration isn't retry
    try {
        for (;;) {
            // 超过尝试次数，则对每个 Segment 加锁
            if (retries++ == RETRIES_BEFORE_LOCK) {
                for (int j = 0; j < segments.length; ++j)
                    ensureSegment(j).lock(); // force creation
            }
            sum = 0L;
            size = 0;
            overflow = false;
            for (int j = 0; j < segments.length; ++j) {
                Segment<K,V> seg = segmentAt(segments, j);
                if (seg != null) {
                    sum += seg.modCount;
                    int c = seg.count;
                    if (c < 0 || (size += c) < 0)
                        overflow = true;
                }
            }
            // 连续两次得到的结果一致，则认为这个结果是正确的
            if (sum == last)
                break;
            last = sum;
        }
    } finally {
        if (retries > RETRIES_BEFORE_LOCK) {
            for (int j = 0; j < segments.length; ++j)
                segmentAt(segments, j).unlock();
        }
    }
    return overflow ? Integer.MAX_VALUE : size;
}
```

#### 3. JDK 1.8 的改动

JDK 1.7 使用分段锁机制来实现并发更新操作，核心类为 Segment，它继承自重入锁 ReentrantLock，并发度与 Segment 数量相等。

JDK 1.8 使用了 CAS 操作来支持更高的并发度，在 CAS 操作失败时使用内置锁 synchronized。

并且 JDK 1.8 的实现也在链表过长时会转换为红黑树。



#### 使用方法

创建和读写
```java
import java.util.Iterator;
import java.util.concurrent.ConcurrentHashMap;
 
public class HashMapExample 
{
    public static void main(String[] args) throws CloneNotSupportedException 
    {
        ConcurrentHashMap<Integer, String> concurrHashMap = new ConcurrentHashMap<>();
         
        //Put require no synchronization
        concurrHashMap.put(1, "A");
        concurrHashMap.put(2, "B");
         
        //Get require no synchronization
        concurrHashMap.get(1);
         
        Iterator<Integer> itr = concurrHashMap.keySet().iterator();
         
        //Using synchronized block is advisable
        synchronized (concurrHashMap) 
        {
            while(itr.hasNext()) {
                System.out.println(concurrHashMap.get(itr.next()));
            }
        }
    }
}
```

使用Collection.synchronizedMap也有同样的方法

```java
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
 
public class HashMapExample 
{
    public static void main(String[] args) throws CloneNotSupportedException 
    {
        Map<Integer, String> syncHashMap = Collections.synchronizedMap(new HashMap<>());
         
        //Put require no synchronization
        syncHashMap.put(1, "A");
        syncHashMap.put(2, "B");
         
        //Get require no synchronization
        syncHashMap.get(1);
         
        Iterator<Integer> itr = syncHashMap.keySet().iterator();
         
        //Using synchronized block is advisable
        synchronized (syncHashMap) 
        {
            while(itr.hasNext()) {
                System.out.println(syncHashMap.get(itr.next()));
            }
        }
    }
}
```