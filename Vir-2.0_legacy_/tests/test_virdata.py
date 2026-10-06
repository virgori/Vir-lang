"""Tests for VirData — dataset, dataloader, transforms."""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.virnn.tensor import Tensor
from src.virdata.dataset import ListDataset
from src.virdata.dataloader import DataLoader
from src.virdata.transforms import Compose, Normalize, Tokenize


def test_list_dataset():
    xs = [Tensor(data=[float(i)], shape=(1,)) for i in range(10)]
    ys = [Tensor(data=[float(i * 2)], shape=(1,)) for i in range(10)]
    ds = ListDataset(xs, ys)
    assert len(ds) == 10
    x, y = ds[3]
    assert x.data == [3.0]
    assert y.data == [6.0]


def test_dataloader_basic():
    xs = [Tensor(data=[float(i), float(i + 1)], shape=(2,)) for i in range(8)]
    ys = [Tensor(data=[float(i)], shape=(1,)) for i in range(8)]
    ds = ListDataset(xs, ys)
    dl = DataLoader(ds, batch_size=4, shuffle=False)

    batches = list(dl)
    assert len(batches) == 2
    bx, by = batches[0]
    assert bx.shape == (4, 2)
    assert by.shape == (4, 1)


def test_dataloader_drop_last():
    xs = [Tensor(data=[float(i)], shape=(1,)) for i in range(7)]
    ys = [Tensor(data=[0.0], shape=(1,)) for _ in range(7)]
    ds = ListDataset(xs, ys)
    dl = DataLoader(ds, batch_size=4, shuffle=False, drop_last=True)
    batches = list(dl)
    assert len(batches) == 1  # 7 // 4 = 1 complete batch


def test_normalize():
    t = Tensor(data=[10.0, 20.0, 30.0], shape=(3,))
    norm = Normalize(mean=[10.0, 20.0, 30.0], std=[1.0, 2.0, 5.0])
    out = norm(t)
    assert abs(out.data[0] - 0.0) < 1e-6
    assert abs(out.data[1] - 0.0) < 1e-6
    assert abs(out.data[2] - 0.0) < 1e-6


def test_compose():
    n1 = Normalize(mean=[0.0], std=[2.0])
    n2 = Normalize(mean=[0.0], std=[0.5])
    pipe = Compose([n1, n2])
    t = Tensor(data=[4.0], shape=(1,))
    out = pipe(t)
    # First normalize: 4/2 = 2.0, second: 2/0.5 = 4.0
    assert abs(out.data[0] - 4.0) < 1e-6


def test_tokenize():
    tok = Tokenize()
    tok.fit(["hello world", "world test"])
    t = tok.encode("hello world", max_len=4)
    assert t.shape == (4,)
    assert t.data[0] > 0  # "hello" mapped to non-zero id
    assert t.data[3] == 0.0  # padding


def test_tokenize_unk():
    tok = Tokenize(vocab={"hello": 1, "world": 2}, unk_id=0)
    t = tok.encode("hello unknown world")
    assert t.data[0] == 1.0
    assert t.data[1] == 0.0  # unknown → unk_id
    assert t.data[2] == 2.0
