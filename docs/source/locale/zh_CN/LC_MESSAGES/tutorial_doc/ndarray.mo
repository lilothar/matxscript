��          |               �      �      �   J        Q    q     s  7   {  +   �  �   �  ~   {  m   �  }  h  2   �       R      A   s  k  �     !     7     J  U   ]     �  ]   3	   Construct a NDArray from arr Constructor Example 1: Pass in a flat list of size 4 and reshape it into a 2x2 matrix. Example 2: Pass in shape as []. Like numpy.array and torch.Tensor, NDArray is a data structure Matx uses to represent a tensor. Currently, we only support simple constructors and data manipulation, and NDArray is primarily used to perform data transfer from Matx to Pytorch/TensorFlow/TVM. NDArray Please refer to the API documentation for more details. The constructor of NDArray has 4 arguments: The device where the NDArray is stored. Supported type: "cpu“, “cuda:%d” and “gpu:%d”, where d is the device number. The default device is "cpu". The shape of the NDArray. It is equivalent to np.array(arr).reshape(shape). If shape is [], the shape will be the same as arr. The type of the data stored in NDArray. Currently, we support int32, int64, float32, float64, uint8 and bool. Project-Id-Version: Matxscript 
Report-Msgid-Bugs-To: 
POT-Creation-Date: 2022-12-10 03:03+0800
PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE
Last-Translator: FULL NAME <EMAIL@ADDRESS>
Language: zh_CN
Language-Team: zh_CN <LL@li.org>
Plural-Forms: nplurals=1; plural=0;
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Transfer-Encoding: 8bit
Generated-By: Babel 2.10.3
 list对象，指定构造出的NDArray的内容。 构造 示例1：指定shape，将传入的一维list变换为指定shape的多维NDArray 示例2：不指定shape，按照传入的list shape构造NDArray NDArray 是我们表示多维矩阵的数据类型，我们目前只实现了简单的数据装载和转换操作。 类似numpy，matx实现了自己的NDArray数据结构来表示多维数组。目前NDArray主要定位为各个深度学习框架(pytorch/tensorflow/tvm)的tensor结构进行桥接数据结构，我们并未在NDArray上定义完备的算子。 多维数组(NDArray) 更多见api文档 构造参数列表 NDArray存储的设配信息，目前支持类型：cpu cuda:%d gpu:%d，默认为cpu list对象，指定构造出的NDArray的shape，可以为[]（空list），为[]时，构造出的NDArray shape和arr相同。 NDArray存储的数据类型，目前支持的类型：int32 int64 float32 float64 uint8 bool 