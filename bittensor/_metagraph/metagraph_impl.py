# The MIT License (MIT)
# Copyright © 2021 Yuma Rao

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, 
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of 
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION 
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
# DEALINGS IN THE SOFTWARE.

import os
import torch
from tqdm import trange

from loguru import logger
from typing import List, Tuple, List

import bittensor
import bittensor.utils.networking as net
import bittensor.utils.weight_utils as weight_utils

class Metagraph( torch.nn.Module ):
    r""" Maintains chain state as a torch.nn.Module.

        Interface:
            tau (:obj:`torch.FloatTensor` of shape :obj:`(1)`): 
                Current, per block, token inflation rate.

            block (:obj:`torch.LongTensor` of shape :obj:`(1)`):
                State block number.

            uids (:obj:`torch.LongTensor` of shape :obj:`(metagraph.n)`):
                UIDs for each neuron.
            
            stake (:obj:`torch.LongTensor` of shape :obj:`(metagraph.n)`):
                Stake balance for each neuron ordered by uid.
                
            lastemit (:obj:`torch.LongTensor` of shape :obj:`(metagraph.n)`):
                Last emission call for each neuron ordered by uid.

            weights (:obj:`torch.FloatTensor` of shape :obj:`(metagraph.n, metagraph.n)`):
                Full weight matrix on chain ordered by uid.

            neurons (:obj:`torch.LongTensor` of shape :obj:`(metagraph.n, -1)`) 
                Tokenized endpoint information.

    """
    def __init__( self, subtensor ):
        r""" Initializes a new Metagraph torch chain interface object.
        """
        super(Metagraph, self).__init__()
        self.subtensor = subtensor
        self.clear()

    def clear( self ) -> 'Metagraph':
        r""" Erases Metagraph state.
        """
        self.version = torch.nn.Parameter( torch.tensor( [ bittensor.__version_as_int__ ], dtype=torch.int64), requires_grad=False )
        self.n = torch.nn.Parameter( torch.tensor( [0], dtype=torch.int64), requires_grad = False )
        self.tau = torch.nn.Parameter( torch.tensor( [0.5], dtype=torch.float32), requires_grad = False )
        self.block = torch.nn.Parameter( torch.tensor( [0], dtype=torch.int64), requires_grad = False )
        self.stake = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.ranks = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.trust = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.consensus = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.incentive = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.inflation = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.dividends = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.active = torch.nn.Parameter(  torch.tensor( [], dtype=torch.int64), requires_grad=False )
        self.lastupdate = torch.nn.Parameter(  torch.tensor( [], dtype=torch.int64), requires_grad=False )
        self.weights = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.bonds = torch.nn.Parameter(  torch.tensor( [], dtype=torch.float32), requires_grad=False )
        self.endpoints = torch.nn.Parameter( torch.tensor( [], dtype=torch.int64), requires_grad=False )
        self._endpoint_objs = None
        return self

    @property
    def S(self) -> torch.FloatTensor:
        return self.stake

    @property
    def R(self) -> torch.FloatTensor:
        return self.ranks

    @property
    def I(self) -> torch.FloatTensor:
        return self.incentive

    @property
    def C(self) -> torch.FloatTensor:
        return self.consensus

    @property
    def T(self) -> torch.FloatTensor:
        return self.trust

    @property
    def D(self) -> torch.FloatTensor:
        return self.dividends

    @property
    def B(self) -> torch.FloatTensor:
        return self.bonds
    
    @property
    def W(self) -> torch.FloatTensor:
        return self.weights

    @property
    def hotkeys( self ) -> List[str]:
        r""" Returns hotkeys for each neuron.
            Returns:
                hotkeys (:obj:`List[str] of shape :obj:`(metagraph.n)`):
                    Neuron hotkeys.
        """
        if self.n.item() == 0:
            return []
        return [ neuron.hotkey for neuron in self.endpoint_objs ]

    @property
    def coldkeys( self ) -> List[str]:
        r""" Returns coldkeys for each neuron.
            Returns:
                coldkeys (:obj:`List[str] of shape :obj:`(metagraph.n)`):
                    Neuron coldkeys.
        """
        if self.n.item() == 0:
            return []
        return [ neuron.coldkey for neuron in self.endpoint_objs ]

    @property
    def modalities( self ) -> List[str]:
        r""" Returns the modality for each neuron.
            Returns:
                coldkeys (:obj:`List[str] of shape :obj:`(metagraph.n)`):
                    Neuron coldkeys.
        """
        if self.n.item() == 0:
            return []
        return [ neuron.modality for neuron in self.endpoint_objs ]

    @property
    def addresses( self ) -> List[str]:
        r""" Returns ip addresses for each neuron.
            Returns:
                coldkeys (:obj:`List[str] of shape :obj:`(metagraph.n)`):
                    Neuron address.
        """
        if self.n.item() == 0:
            return []
        return [ net.ip__str__( neuron.ip_type, neuron.ip, neuron.port ) for neuron in self.endpoint_objs ]

    @property
    def endpoint_objs( self ) -> List['bittensor.Endpoint']:
        r""" Returns endpoints as objects.
            Returns:
                endpoint_obj (:obj:`List[bittensor.Endpoint] of shape :obj:`(metagraph.n)`):
                    Endpoints as objects.
        """
        if self.n.item() == 0:
            return []
        elif self._endpoint_objs != None:
            return self._endpoint_objs
        else:
            self._endpoint_objs = [ bittensor.endpoint.from_tensor( tensor ) for tensor in self.endpoints ]
            return self._endpoint_objs


    def load( self, network:str = None  ) -> 'Metagraph':
        r""" Loads this metagraph object's state_dict from bittensor root dir.
            Args: 
                network: (:obj:`str`, required):
                    Name of state_dict to load, defaults to kusanagi
        """
        try:
            if network == None:
                network = self.subtensor.network
            metagraph_path = '~/.bittensor/' + str(network) + '.pt'
            metagraph_path = os.path.expanduser(metagraph_path)
            if os.path.isfile(metagraph_path):
                self.load_from_path( path = metagraph_path )
            else:
                logger.warning('Did not load metagraph from path: {}, file does not exist. Run metagraph.save() first.', metagraph_path)
        except Exception as e:
            logger.exception(e)
        return self

    def save( self, network:str = None ) -> 'Metagraph':
        r""" Saves this metagraph object's state_dict under bittensor root dir.
            Args: 
                network: (:obj:`str`, required):
                    Name of state_dict, defaults to kusanagi
        """
        if network == None:
            network = self.subtensor.network
        return self.save_to_path( path = '~/.bittensor/', filename = str(network) + '.pt')

    def load_from_path(self, path:str ) -> 'Metagraph':
        r""" Loads this metagraph object with state_dict under the specified path.
            Args: 
                path: (:obj:`str`, required):
                    Path to load state_dict.
        """
        full_path = os.path.expanduser(path)
        metastate = torch.load( full_path )
        return self.load_from_state_dict( metastate )

    def save_to_path(self, path:str, filename:str ) -> 'Metagraph':
        r""" Saves this metagraph object's state_dict to the specified path.
            Args: 
                path: (:obj:`str`, required):
                    Path to save state_dict.
        """
        full_path = os.path.expanduser(path)
        os.makedirs(full_path, exist_ok=True)
        metastate = self.state_dict()
        torch.save(metastate, full_path + '/' + filename)
        return self

    def load_from_state_dict(self, state_dict:dict ) -> 'Metagraph':
        r""" Loads this metagraph object from passed state_dict.
            Args: 
                state_dict: (:obj:`dict`, required):
                    Metagraph state_dict. Must be same as that created by save_to_path.
        """
        self.version = torch.nn.Parameter( state_dict['version'], requires_grad=False )
        self.n = torch.nn.Parameter( state_dict['n'], requires_grad=False )
        self.tau = torch.nn.Parameter( state_dict['tau'], requires_grad=False )
        self.block = torch.nn.Parameter( state_dict['block'], requires_grad=False )
        self.uids = torch.nn.Parameter( state_dict['uids'], requires_grad=False )
        self.stake = torch.nn.Parameter( state_dict['stake'], requires_grad=False )
        self.ranks = torch.nn.Parameter( state_dict['ranks'], requires_grad=False )
        self.trust = torch.nn.Parameter( state_dict['trust'], requires_grad=False )
        self.consensus = torch.nn.Parameter( state_dict['consensus'], requires_grad=False )
        self.incentive = torch.nn.Parameter( state_dict['incentive'], requires_grad=False )
        self.inflation = torch.nn.Parameter( state_dict['inflation'], requires_grad=False )
        self.dividends = torch.nn.Parameter( state_dict['dividends'], requires_grad=False )
        self.active = torch.nn.Parameter( state_dict['active'], requires_grad=False )
        self.lastupdate = torch.nn.Parameter( state_dict['lastupdate'], requires_grad=False )
        self.weights = torch.nn.Parameter( state_dict['weights'], requires_grad=False )
        self.bonds = torch.nn.Parameter( state_dict['bonds'], requires_grad=False )
        self.endpoints = torch.nn.Parameter( state_dict['endpoints'], requires_grad=False )
        self._endpoint_objs = None
        return self

    def sync ( self, block: int = None ) -> 'Metagraph':
        r""" Synchronizes this metagraph with the chain state.
        """
        block = self.subtensor.get_current_block()
        neurons = self.subtensor.neurons()

        # Fill arrays.
        uids = []
        active = []
        stake = []
        ranks = []
        trust = []
        consensus = []
        incentive = []
        inflation = []
        dividends = []
        last_updates = []
        endpoints = []
        weights = []
        bonds = []
        self._endpoint_objs = []
        n_total = len(neurons)
        for n in neurons:
            uids.append( n.uid )
            active.append( n.active )
            stake.append( n.stake / float(1000000000) )
            ranks.append( n.rank / float(1000000000) )
            trust.append( n.trust / float(1000000000) )
            consensus.append( n.consensus / float(1000000000) )
            incentive.append( n.incentive / float(1000000000) )
            inflation.append( n.inflation / float(1000000000) )
            dividends.append( n.dividends )
            last_updates.append( n.last_update )
            endpoint =  bittensor.endpoint(
                uid = int(n.uid), 
                hotkey = str(n.hotkey), 
                ip_type = int(n.ip_type), 
                ip = str(n.ip), 
                port = int(n.port), 
                modality = int(n.modality), 
                coldkey = str(n.coldkey) 
            )
            self._endpoint_objs.append( endpoint )
            endpoints.append( endpoint.to_tensor().tolist())
            if len(n.weights) > 0:
                w_uids, w_weights = zip(*n.weights)
                weights.append( bittensor.utils.weight_utils.convert_weight_uids_and_vals_to_tensor( n_total, w_uids, w_weights ).tolist() )
            else:
                weights.append( [0] * n_total )
            if len(n.bonds) > 0:
                b_uids, b_bonds = zip(*n.bonds)
                bonds.append( bittensor.utils.weight_utils.convert_weight_uids_and_vals_to_tensor( n_total, b_uids, b_bonds ).tolist() )
            else:
                bonds.append( [0] * n_total )

        # Set tensors.
        tn = torch.tensor( n_total, dtype=torch.float32 )
        tblock = torch.tensor( block, dtype=torch.float32 )
        tuids = torch.tensor( uids, dtype=torch.float32 )
        tactive = torch.tensor( active, dtype=torch.float32 )
        tstake = torch.tensor( stake, dtype=torch.float32 )
        tranks = torch.tensor( ranks, dtype=torch.float32 )
        ttrust = torch.tensor( trust, dtype=torch.float32 )
        tconsensus = torch.tensor( consensus, dtype=torch.float32 )
        tincentive = torch.tensor( incentive, dtype=torch.float32 )
        tinflation = torch.tensor( inflation, dtype=torch.float32 )
        tdividends = torch.tensor( dividends, dtype=torch.float32 )
        tlast_update = torch.tensor( last_updates, dtype=torch.int64 )
        tbonds = torch.tensor( bonds, dtype=torch.int64 )
        tweights = torch.tensor( weights, dtype=torch.float32 )
        tendpoints = torch.tensor( endpoints, dtype=torch.int64 )

        # Set params.
        self.n = torch.nn.Parameter( tn, requires_grad=False )
        self.block = torch.nn.Parameter( tblock, requires_grad=False )
        self.uids = torch.nn.Parameter( tuids, requires_grad=False )
        self.stake = torch.nn.Parameter( tstake, requires_grad=False )
        self.ranks = torch.nn.Parameter( tranks, requires_grad=False )
        self.trust = torch.nn.Parameter( ttrust, requires_grad=False )
        self.consensus = torch.nn.Parameter( tconsensus, requires_grad=False )
        self.incentive = torch.nn.Parameter( tincentive, requires_grad=False )
        self.inflation = torch.nn.Parameter( tinflation, requires_grad=False )
        self.dividends = torch.nn.Parameter( tdividends, requires_grad=False )
        self.active = torch.nn.Parameter( tactive, requires_grad=False )
        self.last_update = torch.nn.Parameter( tlast_update, requires_grad=False )
        self.weights = torch.nn.Parameter( tweights, requires_grad=False )
        self.bonds = torch.nn.Parameter( tbonds, requires_grad=False )
        self.endpoints = torch.nn.Parameter( tendpoints, requires_grad=False )
            
        # For contructor.
        return self
    
    def __str__(self):
        return "Metagraph({}, {}, {})".format(self.n.item(), self.block.item(), self.subtensor.network)
        
    def __repr__(self):
        return self.__str__()
        