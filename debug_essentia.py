
import essentia.standard as es
print("Has TensorflowPredict:", hasattr(es, 'TensorflowPredict'))
# List some common keys to see if we have equivalent
print([x for x in dir(es) if 'Tensor' in x or 'Predict' in x])
