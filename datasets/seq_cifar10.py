from random import seed
import torchvision
from torchvision.datasets import CIFAR10
import torchvision.transforms as transforms
from backbone.ResNet18_MAML import resnet18_maml
from backbone.ResNet18 import resnet18
from backbone.Pretrained_ResNet18 import ResNet18
import PIL

from backbone.pc_cnn import PC_CNN
import torch.nn.functional as F
from datasets.seq_tinyimagenet import base_path
from PIL import Image
from datasets.utils.validation import get_train_val
from datasets.utils.continual_dataset import ContinualDataset, store_masked_loaders
from typing import Tuple
from datasets.transforms.denormalization import DeNormalize
import torch
import numpy as np
import os
from torchvision.datasets.utils import download_url, check_integrity
import sys
import pickle
import copy
import torchvision.transforms as transforms

import torchvision.models as models
import torch.nn as nn

# torch.manual_seed(0)
# torch.cuda.manual_seed_all(0)
def uniform_mix_C(mixing_ratio, num_classes):
    '''
    returns a linear interpolation of a uniform matrix and an identity matrix
    '''
    return mixing_ratio * np.full((num_classes, num_classes), 1 / num_classes) + \
        (1 - mixing_ratio) * np.eye(num_classes)
class MyCIFAR10(CIFAR10):
    """
    Overrides the CIFAR10 dataset to change the getitem function.
    """
    def __init__(self, root, train=True, transform=None,
                 target_transform=None, download=False) -> None:
        self.not_aug_transform = transforms.Compose([transforms.ToTensor()])
        super(MyCIFAR10, self).__init__(root, train, transform, target_transform, download)

    def __getitem__(self, index: int) -> Tuple[type(Image), int, type(Image)]:
        """
        Gets the requested element from the dataset.
        :param index: index of the element to be returned
        :returns: tuple: (image, target) where target is index of the target class.
        """
        img, target = self.data[index], self.targets[index]
        # to return a PIL Image
        img = Image.fromarray(img, mode='RGB')
        original_img = img.copy()
        not_aug_img = self.not_aug_transform(original_img)

        if self.transform is not None:
            img = self.transform(img)

        if self.target_transform is not None:
            target = self.target_transform(target)

        if hasattr(self, 'logits'):
            return img, target, not_aug_img, self.logits[index]
        return img, target, not_aug_img

class SequentialCIFAR10(ContinualDataset):
    # 继承自ContinualDataset, 因此有 self.i = 0
    NAME = 'seq-cifar10'
    SETTING = 'class-il'
    N_CLASSES_PER_TASK = 2
    N_TASKS = 5
    task_id = 0
    TRANSFORM = transforms.Compose(
            [transforms.RandomCrop(32, padding=4),
             transforms.RandomHorizontalFlip(),
             transforms.ToTensor(),
             transforms.Normalize((0.4914, 0.4822, 0.4465),
                                  (0.2470, 0.2435, 0.2615))])


    def get_data_loaders(self, tag=False):
        transform = self.TRANSFORM
        test_transform = transforms.Compose(
            [transforms.ToTensor(), self.get_normalization_transform()])

        train_dataset = MyCIFAR10(base_path() + 'CIFAR10', train=True,
                                  download=True, transform=transform)


        if self.args.validation:
            train_dataset, test_dataset = get_train_val(train_dataset,
                                                    test_transform, self.NAME)
        else:
            test_dataset = CIFAR10(base_path() + 'CIFAR10',train=False,
                                   download=True, transform=test_transform)
        train, test = store_masked_loaders(train_dataset, test_dataset, self, tag)
        return train, test

    @staticmethod
    def get_transform():
        transform = transforms.Compose(
            [transforms.ToPILImage(), SequentialCIFAR10.TRANSFORM])
        return transform

    @staticmethod
    def get_backbone(eman1):
        return resnet18_maml(SequentialCIFAR10.N_CLASSES_PER_TASK
                        * SequentialCIFAR10.N_TASKS, eman=eman1) #PC_CNN
    # def get_backbone():
    #     return PC_CNN(3*32*32,SequentialCIFAR10.N_CLASSES_PER_TASK * SequentialCIFAR10.N_TASKS)

    @staticmethod
    def get_loss():
        return F.cross_entropy
        # return nn.CrossEntropyLoss(reduction='none')
    
    @staticmethod
    def get_normalization_transform():
        transform = transforms.Normalize((0.4914, 0.4822, 0.4465),
                                         (0.2470, 0.2435, 0.2615))
        return transform

    @staticmethod
    def get_denormalization_transform():
        transform = DeNormalize((0.4914, 0.4822, 0.4465),
                                (0.2470, 0.2435, 0.2615))
        return transform

    @staticmethod
    def get_scheduler(model, args):
        return None
