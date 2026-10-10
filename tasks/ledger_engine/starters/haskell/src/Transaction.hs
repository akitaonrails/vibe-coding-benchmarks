{-# LANGUAGE OverloadedStrings #-}
module Transaction where
import Domain
import Table
import Data.Text (Text)
import qualified Data.Map.Strict as M
import qualified Data.Set as S

data Transaction = Transaction { owner :: Text, snapshotRevision :: Int, snapshot :: Table,
  writes :: M.Map Text (Maybe Row), points :: S.Set Text,
  ranges :: M.Map (Text,Text) (M.Map Text Int), aliases :: M.Map Text (M.Map Text Int) } deriving Show
begin :: Text -> Int -> Table -> Transaction
begin tenant revision table = Transaction tenant revision table M.empty S.empty M.empty M.empty
overlay :: Table -> Int -> Transaction -> Table
overlay table revision tx = M.foldrWithKey (\ident value -> M.insert (Key (owner tx) ident) (Entry revision value)) table (writes tx)
readRow :: Text -> Transaction -> (Maybe Row,Transaction)
readRow ident tx = (M.findWithDefault (row (owner tx) ident (snapshot tx)) ident (writes tx),tx { points=S.insert ident (points tx) })
scan :: Text -> Text -> Transaction -> ([Row],Transaction)
scan lo hi tx
  | lo>=hi = ([],tx)
  | otherwise = ([r|r<-live (owner tx) (overlay (snapshot tx) (snapshotRevision tx) tx),lo<=rowId r,rowId r<hi],tx { ranges=M.insert (lo,hi) (interval (owner tx) lo hi (snapshot tx)) (ranges tx) })
lookupAlias :: Text -> Transaction -> ([Row],Transaction)
lookupAlias name tx = ([r|r<-live (owner tx) (overlay (snapshot tx) (snapshotRevision tx) tx),alias r==Just name],tx { aliases=M.insert name (aliasVersions (owner tx) name (snapshot tx)) (aliases tx) })
frames :: Text -> Int -> Transaction -> [Frame]
frames request revision tx = [BeginFrame (owner tx) request revision (M.size (writes tx))]
  ++ [EditFrame ident value | (ident,value)<-M.toAscList (writes tx)] ++ [SealFrame revision]
