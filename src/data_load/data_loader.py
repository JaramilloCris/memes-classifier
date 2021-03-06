from torchvision import transforms
from torch.utils.data import Dataset
from torch.nn.utils.rnn import pad_sequence
from PIL import Image
from src.utils.utils import make_weights_for_balanced_classes
from transformers import BertTokenizer

import os
import torch
import random


from src.tokenizers.tokenizer import TokenizerMeme
from deep_translator import GoogleTranslator
from googletrans import Translator


torch.manual_seed(42)


class ImageTextData(Dataset):
    
    """
    Custom Dataset for images and text of meme dataset
    
    """

    def __init__(self, df: str, transform: bool=False,
                 only_meme: bool=False, imagen_out: bool=True,
                 data_aug: bool=False,
                 bert: bool=False,):

        # Dict with the initial info
        self.df = df

        # Vocab for text data
        self.vocab = df["vocab"]
        self.vocab["<pad>"] = 1

        self.image_out = imagen_out
        self.data_aug = data_aug
        self.only_meme = only_meme
        self.tokenizer = TokenizerMeme(self.vocab)
        self.translator = Translator()
        self.bert = bert
        self.bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        
        self.transforms = transforms.Compose([transforms.Resize((56, 56)),
                                              transforms.ToTensor(),
                                              transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])

        # Data iterator
        self.image_path = []
        self.image = []
        self.text = []
        self.targets = []
        self.text_bert = []
        self.mask_bert = []
        
        self.keys_vocab = list(self.vocab.keys())
        self.values_vocab = list(self.vocab.values())
        
        # Process data
        for i, (image_id, text, target) in enumerate(zip(df["images"]["img_ids"],
                                                         df["images"]["texts"],
                                                         df["images"]["targets"])):

            targets_name = df["targets_names"][str(target)]
            
            # If target is dudoso, omit
            if targets_name != "Dudoso":
                path_image = f"./{targets_name}{os.sep}img_{str(image_id).zfill(7)}.jpg"

                # If the image is not in the folder, omit
                if os.path.exists(path_image):
                
                    image = self.process_image(path_image)
                    text = self.process_text(text)
                    target = self.process_labels(target)
                    
                    # Data Augmentation
                    if self.data_aug:
                        self.data_augmentation(image, text, target)

        self.text = pad_sequence(self.text,
                                         batch_first=True,
                                         padding_value=self.vocab["<pad>"])
        

    def __len__(self) -> int:
        
        """
        Get length of dataset
        
        return: int -> length of dataset
        """
        
        return len(self.image)

    def __getitem__(self, index: int) -> tuple:
        
        """
        Get item from dataset with index
        Its for iterator
        
        :param index: int -> index of item
        
        return: tuple -> (image, text, target)
        
        """

        image = self.image[index]
        label = self.targets[index]
        text = self.text[index]

        if self.bert:  
            text_bert = self.text_bert[index]
            mask_bert = self.mask_bert[index]
            return image, text, text_bert, mask_bert, label
        
        return image, text, label
    
    def get_transform(self) -> transforms.Compose:
        return self.transform
    
    def get_vocab(self) -> dict:
        return self.tokenizer.get_vocab()
    
    def process_image(self, path_image):
        
        """
        Process image and save in the Loader
        
        :param path_image: str -> path of image
        
        :return image: PIL.Image -> image
        
        """
        
        image = Image.open(path_image).convert("RGB")
        if self.transforms is not None:
            image_tensor = self.transforms(image)
        self.image.append(image_tensor)
        self.image_path.append(path_image)
        
        return image
        
        
    def process_text(self, text):
        
        """
        Process text and save in the Loader
        
        :param text: str -> text to process
        
        :return text: list -> list of tokens
        
        """
        
        
        text_tensor = torch.tensor(text)
        self.text.append(text_tensor)
        
        text_str = ''
        for id_text in text:
            text_str += f"{self.keys_vocab[self.values_vocab.index(id_text)]} "
            
        encoded = self.bert_tokenizer.encode_plus(
            text=text_str,
            add_special_tokens=True,
            max_length = 16,
            pad_to_max_length = True,            
            return_attention_mask = True,
            return_tensors='pt',
        )
            
        self.text_bert.append(encoded['input_ids'].flatten())
        self.mask_bert.append(encoded['attention_mask'].flatten())
        
        return text_str[:-1]
        
        
    def process_labels(self, target):
        
        """
        Save correct target 
        
        :param target: int -> target input of image
        
        :return target: int -> real target of image
        
        """
        
        if target == 4:
            if self.only_meme:
                self.targets.append(0)
                return 0
            else:
                self.targets.append(2)
                return 2
            
        else:
            self.targets.append(target - 1)
            return target -1
            
    def data_augmentation(self, image, text, target):
        
        """
        Process text and select type of augmentation
        
        :param image: PIL image
        :param text: str -> text of image
        :param target: int -> target of image
        
        """
        
        try:
        
            if len(text) >= 3 or len(text) == 0:
        
                tensor_text, aug_method = [], []
                if text != "":
                    
                    text = self.tokenizer.clean_text(text)                                            
                    text_translate = GoogleTranslator(source='auto', target='es').translate(text)
                    if text_translate == text:
                        text_translate = GoogleTranslator(source='es', target='en').translate(text_translate)
                        
                    if text == text_translate:
                        return False
                    
                    tensor_text = self.tokenizer.tokenize(text_translate)
                    
                tensor_text = torch.tensor(tensor_text)
                
                aug_method.append(transforms.RandomResizedCrop(56)) if random.random() < 0.5 else aug_method.append(transforms.RandomCrop(56))
                aug_method.append(transforms.RandomHorizontalFlip()) if random.random() < 0.5 else aug_method.append(transforms.RandomVerticalFlip())
                
                self.image_random_aug(image, aug_method)
                self.text.append(tensor_text)
                self.targets.append(target)
                
                # if value_alt <= 0.5:
                    
                #     self.image_random_aug(image, transforms.transforms.RandomResizedCrop(224))
                #     self.text.append(tensor_text)
                #     self.targets.append(target)
                
                # else:
                #     self.image_random_aug(image, transforms.Pad(padding=50))
                #     self.text.append(tensor_text)
                #     self.targets.append(target)
                    
        except Exception as e:
            print("No codificado", text, e)
        
                                        
    def image_random_aug(self, image, method):
        
        """
        Apply random augmentation to image and save in self.image
        
        :param image: PIL.Image -> image to apply augmentation
        :para method: list -> list of augmentation methods
        
        :return: Tensor -> image with augmentation
        
        """
        
        trans = transforms.Compose([transforms.Resize((56, 56)),
                                    method[0],
                                    method[1],
                                    transforms.ToTensor(),
                                    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])

        image_tensor = trans(image)
        self.image.append(image_tensor)
        return image_tensor

def load_split_data(datadir: str, batch_size: int=64, test_size: float=.2, imagen_out: bool=True, data_aug=False, bert: bool = True) -> tuple:
    
    """
    Create the split dataset for train an test with test_size
    Balanced classes for underfitting and overfitting
    
    :param datadir: str -> path to data
    :param bath_size: int -> batch size
    :param test_size: float -> test size
    :param imagen_out: bool -> if true, return image, else text
    
    return: tuple -> (train_data, test_data)
    
    """

    model_dataset = ImageTextData(datadir,
                                  imagen_out=imagen_out,
                                  data_aug=data_aug,
                                  bert=bert)
                                  

    total_lenght = len(model_dataset)
    test_lenght = int(total_lenght * test_size)
    train_lenght = total_lenght - test_lenght

    train_data, test_data = torch.utils.data.random_split(model_dataset,
                                                          [train_lenght, test_lenght])

    weights_train = make_weights_for_balanced_classes(train_data.dataset.targets,
                                                      train_data.indices,
                                                      3)
    weights_train = torch.DoubleTensor(weights_train)
    sampler_train = torch.utils.data.sampler.WeightedRandomSampler(
        weights_train, len(weights_train))

    weights_test = make_weights_for_balanced_classes(
        train_data.dataset.targets, test_data.indices, 3)
    weights_test = torch.DoubleTensor(weights_test)
    sampler_test = torch.utils.data.sampler.WeightedRandomSampler(
        weights_test, len(weights_test))

    trainloader = torch.utils.data.DataLoader(train_data,
                                              sampler=sampler_train,
                                              batch_size=batch_size,
                                              #collate_fn=generate_batch
                                              )
    testloader = torch.utils.data.DataLoader(test_data,
                                             batch_size=batch_size,
                                             #collate_fn=generate_batch
                                             )
    return trainloader, testloader, model_dataset.get_vocab()


def generate_batch(batch: tuple) -> tuple:
    
    """
    Function for generate batch for data loader
    Load and transform image
    Creade pad_sequence for text
    
    :param batch: tuple -> (image, text, target)
    
    return: tuple -> (image, text, target)
    
    """

    label_list, text_list, image_list, text_bert, mask_bert = [], [], [], [], []
    for (_image, _text, _text_bert, _mask_bert, _label) in batch:
        label_list.append(_label)
        text_list.append(_text)
        image_list.append(_image)



    return (
        torch.stack(image_list),
        pad_sequence(text_list, batch_first=True, padding_value=1),

        torch.tensor(label_list)
    )
    