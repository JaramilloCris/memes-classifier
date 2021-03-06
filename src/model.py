from tkinter.tix import TEXT
import torch.nn as nn
import torch.nn.functional as F
import torch
    
from torchvision import models
from stop_words import get_stop_words
    

class CNN(nn.Module): 

    def __init__(self, out_size):
        super(CNN, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=3, out_channels=10, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(10, 20, kernel_size=3, padding=1)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(3920, 512)
        self.fc2 = nn.Linear(512, out_size)

    def forward(self, x):

        x = F.relu(F.max_pool2d(self.conv1(x), 2))
        x = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x)), 2))
        x = x.view(x.shape[0], -1)
        x = F.relu(self.fc1(x))
        x = F.dropout(x, training=self.training)
        x = self.fc2(x)
        return x


class CNN_CATEGORY(nn.Module): 

    def __init__(self, out_classes):
        super(CNN_CATEGORY, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=3, out_channels=10, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(10, 20, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(20, 30, kernel_size=3, padding=1)
        self.max_pool1 = nn.MaxPool2d((3,3), stride=2, padding=1)
        self.conv2_drop = nn.Dropout2d()
        self.fc1 = nn.Linear(1470, 1024)
        self.fc2 = nn.Linear(1024, 512)
        self.fc3 = nn.Linear(512, 256)
        self.out = nn.Linear(256, out_classes)

    def forward(self, x):
        x = F.relu(self.max_pool1(self.conv1(x)))
        x = F.relu(self.max_pool1(self.conv2_drop(self.conv2(x))))
        x = F.relu(self.max_pool1(self.conv2_drop(self.conv3(x))))
        x = x.view(x.shape[0],-1)
        x = F.relu(self.fc1(x))
        x = F.dropout(x, training=self.training)
        x = self.fc2(x)
        x = F.dropout(x, training=self.training)
        x = self.fc3(x)
        x = self.out(x)
        return x

class ImageClassificator(nn.Module):
    
    def __init__(self):
        
        super().__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(44944, 512)
        self.fc2 = nn.Linear(512, 256)
        self.soft = nn.Softmax(dim=1)
        
    def forward(self, x):
        
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = torch.flatten(x, 1)  # flatten all dimensions except batch
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return x
    
    
def get_restnet152(gradient=True):
    
    model = models.resnet152(pretrained=True)
    for param in model.parameters():
        param.requires_grad = gradient
    
    model.fc = nn.Sequential(nn.Linear(2048, 256),)
                                    #  nn.LogSoftmax(dim=1))
    
    return model
    
    
class BoWClassifier(nn.Module):
    
    def __init__(self, vocab_size, num_class):
        
        super(BoWClassifier, self).__init__()
        self.linear1 = nn.Linear(vocab_size, num_class)
                
    def forward(self, bow_vec):
        
        out = self.linear1(bow_vec)
        return out  
    
    
def make_bow_vector(batch, vocab):
    
    stop_words = get_stop_words('es')
    ret = []
    for sentence in batch:
        vec = torch.zeros(len(vocab))
        for word in str(sentence).split():
            word = word.lower()
            if word not in stop_words:
                vec[vocab[word]] += 1
        
        ret.append(vec.view(1, -1))
        
    return tuple(ret)


def make_target(batch, classes):
    
    ret = []
    for label in batch:
        ret.append(torch.LongTensor([classes[label]]))
        
    return tuple(ret)


class TextSentimentLinear(nn.Module):
    def __init__(self, vocab_size, embed_dim, out_size, vocab):
        super().__init__()
        self.vocab = vocab
        self.embedding = nn.EmbeddingBag(vocab_size, embed_dim, mode="max")
        self.fc = nn.Linear(embed_dim, out_size)
        #self.init_weights() # probar agregando esto
        self.act = nn.ReLU()

    def init_weights(self): 
        initrange = 0.5
        self.embedding.weight.data.uniform_(-initrange, initrange)
        self.embedding.weight.data[1].zero_()
        self.fc.weight.data.uniform_(-initrange, initrange)
        self.fc.bias.data.zero_()

    def forward(self, text):
        # text -> B, N

        # embedded -> B, embed_dim
        embedded = self.embedding(text)

        # B, num_class
        return self.fc(embedded)


class SpatialDropout(nn.Dropout2d):
    def forward(self, x):
        x = x.unsqueeze(2)    # (N, T, 1, K)
        x = x.permute(0, 3, 2, 1)  # (N, K, 1, T)
        x = super(SpatialDropout, self).forward(x)  # (N, K, 1, T), some features are masked
        x = x.permute(0, 3, 2, 1)  # (N, T, 1, K)
        x = x.squeeze(2)  # (N, T, K)
        return x


class LSTMTagger(nn.Module):

    def __init__(self, embedding_dim, vocab_size, out_size, vocab, lstm_units=128):
        super(LSTMTagger, self).__init__()
        LSTM_UNTITS = lstm_units
        DENSE_HIDDEN_UNITS = 4 * LSTM_UNTITS
        
        self.embedding = nn.Embedding(vocab_size,
                                      embedding_dim,
                                      padding_idx=1)
        self.embedding_dropout = SpatialDropout(0.3)

        # The LSTM takes word embeddings as inputs, and outputs hidden states
        # with dimensionality hidden_dim.
        self.lstm1 = nn.LSTM(embedding_dim,
                             LSTM_UNTITS,
                             batch_first=True,
                             bidirectional=True)
        
        self.lstm2 = nn.LSTM(LSTM_UNTITS * 2,
                             LSTM_UNTITS,
                             batch_first=True,
                             bidirectional=True)

        # The linear layer that maps from hidden state space to tag space
        self.linear1 = nn.Linear(DENSE_HIDDEN_UNITS, DENSE_HIDDEN_UNITS)
        self.linear2 = nn.Linear(DENSE_HIDDEN_UNITS, DENSE_HIDDEN_UNITS)
        
        #self.linear_out = nn.Linear(DENSE_HIDDEN_UNITS, 1)
        self.linear_aux_out = nn.Linear(DENSE_HIDDEN_UNITS, out_size)
           
    def forward(self, sentence):
        
        h_embedding = self.embedding(sentence)
        h_embedding = self.embedding_dropout(h_embedding)
        
        h_lstm1, _ = self.lstm1(h_embedding)
        h_lstm2, _ = self.lstm2(h_lstm1)
        
        # global average pooling
        avg_pool = torch.mean(h_lstm2, 1)
        # global max pooling
        max_pool, _ = torch.max(h_lstm2, 1)
        
        h_conc = torch.cat((max_pool, avg_pool), 1)
        h_conc_linear1 = F.relu(self.linear1(h_conc))
        h_conc_linear2 = F.relu(self.linear2(h_conc))
        
        hidden = h_conc + h_conc_linear1 + h_conc_linear2
        
        #result = self.linear_out(hidden)
        aux_result = self.linear_aux_out(hidden)
        #out = torch.cat([result, aux_result], 1)
        
        return aux_result
    
    
class TextSentimentConv1d(nn.Module):
    def __init__(self, vocab_size, embed_dim, out_size, vocab):
        super().__init__()
        self.embedding = nn.Embedding(
            vocab_size,
            embed_dim,
            padding_idx=vocab["<pad>"]
        )
        self.conv = nn.Conv1d(
            in_channels=1,
            out_channels=out_size,
            kernel_size=3*embed_dim,
            stride=embed_dim
        )
    
    def forward(self, text):
        # embedded -> B, N, E
        embedded = self.embedding(text)
        embedded = embedded.view(embedded.shape[0], 1, -1)
        z = F.relu(self.conv(embedded))
        return z.max(dim=-1).values
    
    
    
class RNN(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_size, vocab):
        super().__init__()
        
        self.embedding = nn.Embedding(
            vocab_size,
            embed_dim,
            padding_idx=vocab["<pad>"]
        )
        
        self.rnn = nn.RNN(
            input_size=embed_dim,
            hidden_size=hidden_size,
            bidirectional=True,
            batch_first=True
        )
        
        self.label = nn.Linear(2*hidden_size, 256)
        
        
    def forward(self, text):
        
        embedded = self.embedding(text)
        output, hidden = self.rnn(embedded)
        hidden = hidden.view(hidden.size(1), -1)
        
        out = self.label(hidden)
        return out
    
class BertModelClassification(nn.Module):
    
    def __init__(self, bert, out_size):
        
        super(BertModelClassification, self).__init__()
        self.bert= bert        
        self.out_size = out_size
        self.drop = nn.Dropout(0.2)
        self.out = nn.Linear(self.bert.config.hidden_size, out_size)
        self.act = nn.Softmax(dim=1)
        
        
    def forward(self, text, attention):
        h = self.bert(input_ids = text, attention_mask = attention).last_hidden_state
        h_cls = h[:, 0]
        out = self.drop(h_cls)
        out = self.out(out)

        
        return out
        
class ModelMix(nn.Module):
    
    def __init__(self, model_text, model_image, input_size, out_size):
        
        super(ModelMix, self).__init__()
        self.model_text = model_text
        self.model_image = model_image
        self.lineal1 = nn.Linear(input_size, out_size)
        self.act = nn.Softmax(dim=1)
        
    def forward(self, image, text):
        
        text_process = self.model_text(text)
        image_process = self.model_image(image)
        out = torch.cat([text_process, image_process], 1)
        out = self.lineal1(out)
        return out


class ModelMixBert(nn.Module):
    
    def __init__(self, model_image, bert, input_size, out_size):
        
        super(ModelMixBert, self).__init__()
        self.bert = bert
        self.model_image = model_image
        self.out_size = out_size
        self.drop = nn.Dropout(0.2)
        self.out = nn.Linear(input_size, out_size)
        
        
    def forward(self, image, text, attention):
        
        text_process = self.bert(text, attention)
        image_process = self.model_image(image)
        out = torch.cat([text_process, image_process], 1)
        out = self.out(out)

        return out