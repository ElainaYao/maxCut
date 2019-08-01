#!/usr/bin/python
# -*- coding: UTF-8 -*-

import matplotlib
matplotlib.use('Agg')

# Pytorch requirements
import unicodedata
import string
import re
import random

import torch
import torch.nn as nn
from torch.nn import init
from torch.autograd import Variable
from torch import optim
import torch.nn.functional as F

if torch.cuda.is_available():
    dtype = torch.cuda.FloatTensor
    dtype_l = torch.cuda.LongTensor
else:
    dtype = torch.FloatTensor                      # why FloatTensor??
    dtype_l = torch.cuda.LongTensor

######## need to go back and write my own 
def GMul(W, x):
    # x is a tensor of size (bs, N, num_features)
    # W is a tensor of size (bs, N, N, J)
    x_size = x.size()
    # print (x)
    W_size = W.size()
    N = W_size[-3]
    J = W_size[-1]
    W_lst = W.split(1, 3)
    # print (len(W_lst))
    if N > 5000:
        output_lst = []
        for W in W_lst:
            output_lst.append(torch.bmm(W.squeeze(3),x))
        output = torch.cat(output_lst, 1)
    else:
        W = torch.cat(W_lst, 1).squeeze(3) # W is now a tensor of size (bs, J*N, N)
        output = torch.bmm(W, x) # output has size (bs, J*N, num_features)
    output = output.split(N, 1)
    output = torch.cat(output, 2) # output has size (bs, N, J*num_features)
    return output

######## need to go back and write my own
class gnn_atomic_lg(nn.Module):
    def __init__(self, feature_maps, J):
        super(gnn_atomic_lg, self).__init__()
        self.feature_maps = feature_maps
        self.J = J
        self.fcx2x_1 = nn.Linear(J * feature_maps[0], feature_maps[2])
        self.fcy2x_1 = nn.Linear(2 * feature_maps[1], feature_maps[2])
        self.fcx2x_2 = nn.Linear(J * feature_maps[0], feature_maps[2])
        self.fcy2x_2 = nn.Linear(2 * feature_maps[1], feature_maps[2])
        self.fcx2y_1 = nn.Linear(J * feature_maps[1], feature_maps[2])
        self.fcy2y_1 = nn.Linear(4 * feature_maps[2], feature_maps[2])
        self.fcx2y_2 = nn.Linear(J * feature_maps[1], feature_maps[2])
        self.fcy2y_2 = nn.Linear(4 * feature_maps[2], feature_maps[2])
        self.bn2d_x = nn.BatchNorm2d(2 * feature_maps[2])
        self.bn2d_y = nn.BatchNorm2d(2 * feature_maps[2])

    def forward(self, WW, x, WW_lg, y, P):
        xa1 = GMul(WW, x) # out has size (bs, N, num_inputs)
        xa1_size = xa1.size()
        xa1 = xa1.contiguous()
        # print ('xa1', xa1.shape)
        # print ('J', self.J)
        # print ('fm0', self.feature_maps[0])
        xa1 = xa1.view(-1, self.J * self.feature_maps[0])
        # print (x.size()) 
        # print ('x2x', x2x)
        # xa1 = xa1.type(dtype)

        xb1 = GMul(P, y)
        # xb1 = xb1.size()
        xb1 = xb1.contiguous()
        # print ('xb1', xb1.shape)
        xb1 = xb1.view(-1, 2 * self.feature_maps[1])

        z1 = F.relu(self.fcx2x_1(xa1) + self.fcy2x_1(xb1)) # has size (bs*N, num_outputs)

        yl1 = self.fcx2x_2(xa1) + self.fcy2x_2(xb1)
        zb1 = torch.cat((yl1, z1), 1)
        zc1 = self.bn2d_x(zb1.unsqueeze(2).unsqueeze(3)).squeeze(3).squeeze(2)
        # print ('zc1', zc1.shape)
        zc1 = zc1.view(*xa1_size[:-1], 2 * self.feature_maps[2])
        # print ('zc1', zc1.shape)
        x_output = zc1

        xda1 = GMul(WW_lg, y)
        xda1_size = xda1.size()
        xda1 = xda1.contiguous()
        # print ('xda1', xda1.shape)
        xda1 = xda1.view(-1, self.J * self.feature_maps[1])

        xdb1 = GMul(torch.transpose(P, 2, 1), zc1)
        # xdb1_size = xdb1.size()
        xdb1 = xdb1.contiguous()
        # print ('xdb1', xdb1.shape)
        xdb1 = xdb1.view(-1, 4 * self.feature_maps[2])

        zd1 = F.relu(self.fcx2y_1(xda1) + self.fcy2y_1(xdb1))

        ydl1 = self.fcx2y_2(xda1) + self.fcy2y_2(xdb1)

        zdb1 = torch.cat((ydl1, zd1), 1)
        # y_output = self.bn2d_x(y_cat)
        zdc1 = self.bn2d_y(zdb1.unsqueeze(2).unsqueeze(3)).squeeze(3).squeeze(2)

        # print ('zdc1', zdc1.shape)
        zdc1 = zdc1.view(*xda1_size[:-1], 2 * self.feature_maps[2])
        y_output = zdc1
        return WW, x_output, WW_lg, y_output, P

class gnn_atomic_lg_final(nn.Module):
    def __init__(self, feature_maps, J, n_classes):
        super(gnn_atomic_lg_final, self).__init__()
        self.num_inputs = J*feature_maps[0]
        self.num_inputs_2 = 2 * feature_maps[1]
        self.num_outputs = n_classes
        self.fcx2x_1 = nn.Linear(self.num_inputs, self.num_outputs)
        self.fcy2x_1 = nn.Linear(self.num_inputs_2, self.num_outputs)

    def forward(self, W, x, W_lg, y, P):
        # print ('W size', W.size())
        # print ('x size', input[1].size())
        x2x = GMul(W, x) # out has size (bs, N, num_inputs)
        x2x_size = x2x.size()
        # print (x_size)
        x2x = x2x.contiguous()
        x2x = x2x.view(-1, self.num_inputs)
        # print (x.size()) 

        # y2x = torch.bmm(P, y)
        y2x = GMul(P, y)
        y2x_size = x2x.size()
        y2x = y2x.contiguous()
        y2x = y2x.view(-1, self.num_inputs_2)

        # xy2x = x2x + y2x 
        xy2x = self.fcx2x_1(x2x) + self.fcy2x_1(y2x) # has size (bs*N, num_outputs)

        x_output = xy2x.view(*x2x_size[:-1], self.num_outputs)

        return W, x_output


class lGNN_multiclass(nn.Module):
    def __init__(self, num_features, num_layers, J, n_classes=2):
        super(lGNN_multiclass, self).__init__()
        self.num_features = num_features
        self.num_layers = num_layers
        self.featuremap_in = [1, 1, num_features // 2]
        self.featuremap_mi = [num_features, num_features, num_features // 2]
        self.featuremap_end = [num_features, num_features, 1]
        # self.layer0 = Gconv(self.featuremap_in, J)
        self.layer0 = gnn_atomic_lg(self.featuremap_in, J)
        for i in range(num_layers):
            # module = Gconv(self.featuremap_mi, J)
            module = gnn_atomic_lg(self.featuremap_mi, J)
            self.add_module('layer{}'.format(i + 1), module)
        self.layerlast = gnn_atomic_lg_final(self.featuremap_end, J, n_classes)

    def forward(self, W, x, W_lg, y, P):
        cur = self.layer0(W, x, W_lg, y, P)
        for i in range(self.num_layers):
            # print ('layer', i)
            cur = self._modules['layer{}'.format(i+1)](*cur)
        out = self.layerlast(*cur)
        return out[1]


if __name__ == '__main__':
    # test modules
    bs =  4
    num_features = 10
    num_layers = 5
    N = 8
    x = torch.ones((bs, N, num_features))
    W1 = torch.eye(N).unsqueeze(0).unsqueeze(-1).expand(bs, N, N, 1)
    W2 = torch.ones(N).unsqueeze(0).unsqueeze(-1).expand(bs, N, N, 1)
    J = 2
    W = torch.cat((W1, W2), 3)
    input = [Variable(W), Variable(x)]
