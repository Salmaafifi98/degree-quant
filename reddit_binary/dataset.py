import torch
from torch_geometric.datasets import Planetoid
from torch_geometric.utils import degree
import torch_geometric.transforms as T

from degree.dq.transforms import ProbabilisticHighDegreeMask


# Follows the setup used by PyTorch Geometric


class NormalizedDegree(object):
    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def __call__(self, data):
        deg = degree(data.edge_index[0], dtype=torch.float)
        deg = (deg - self.mean) / self.std
        data.x = deg.view(-1, 1)
        return data


def get_dataset(path, name, sparse=True, cleaned=False, DQ=None):
    # dataset = Planetoid(path, name, cleaned=cleaned)
    dataset = Planetoid(root='/tmp/Cora', name='Cora')
    dataset.data.edge_attr = None

    if dataset.data.x is None:
        max_degree = 0
        degs = []
        for data in dataset:
            degs += [degree(data.edge_index[0], dtype=torch.long)]
            max_degree = max(max_degree, degs[-1].max().item())

        if max_degree < 1000:
            dataset.transform = T.OneHotDegree(max_degree)
        else:
            deg = torch.cat(degs, dim=0).to(torch.float)
            mean, std = deg.mean().item(), deg.std().item()
            dataset.transform = NormalizedDegree(mean, std)

    if not sparse:
        num_nodes = max_num_nodes = 0
        for data in dataset:
            num_nodes += data.num_nodes
            max_num_nodes = max(data.num_nodes, max_num_nodes)

        # Filter out a few really large graphs in order to apply DiffPool.
        if name == "Cora":
            num_nodes = min(int(num_nodes / len(dataset) * 1.5), max_num_nodes)
        else:
            num_nodes = min(int(num_nodes / len(dataset) * 5), max_num_nodes)

        indices = []
        for i, data in enumerate(dataset):
            if data.num_nodes <= num_nodes:
                indices.append(i)
        dataset = dataset[torch.tensor(indices)]

        if dataset.transform is None:
            dataset.transform = T.ToDense(num_nodes)
        else:
            dataset.transform = T.Compose([dataset.transform, T.ToDense(num_nodes)])

    if DQ is not None:
        print(f"Generating ProbabilisticHighDegreeMask: {DQ}")
        dq_transform = ProbabilisticHighDegreeMask(
            DQ["prob_mask_low"], min(DQ["prob_mask_low"] + DQ["prob_mask_change"], 1.0)
        )
        # NOTE: see issue #1 if you are customizing for your own dataset
        # dataset.transform may be None (not the case here)
        dataset.transform = T.Compose([dataset.transform, dq_transform])

    return dataset
