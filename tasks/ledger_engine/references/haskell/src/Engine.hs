{-# LANGUAGE OverloadedStrings #-}
module Engine where
import Domain
import Table hiding (version)
import Transaction
import qualified Device as D
import Data.Aeson hiding (Key)
import Data.Text (Text)
import qualified Data.Map.Strict as M

data Engine = Engine { device :: D.Device, table :: Table, receipts :: Receipts, revision :: Int, transactions :: M.Map Text Transaction } deriving Show
reset :: Int -> Engine
reset c = Engine (D.emptyDevice c) M.empty M.empty 0 M.empty
recoverEngine :: Engine -> Engine
recoverEngine e = let (t,rs,r,d)=D.recover (device e) in Engine d t rs r M.empty
image :: Engine -> Value
image e = obj [("schema",int 2),("revision",int (revision e)),("entries",imageEntries (table e)),("receipts",arr [obj [("tenant",String t),("request",String q),("revision",int r)] | (Key t q,r)<-M.toAscList (receipts e)])]
fault :: Value -> Maybe Value
fault request = if has "fault" request then Just (field "fault" request) else Nothing
commit :: Value -> Text -> Engine -> (Value,Engine)
commit request tenant e
  | Just previous <- M.lookup identity (receipts e) = (obj [("committed",int previous)],e)
  | Nothing <- M.lookup handle (transactions e) = (err "transaction_missing",e)
  | Just tx <- M.lookup handle (transactions e), owner tx/=tenant = (err "transaction_owner",e)
  | Just tx <- M.lookup handle (transactions e) = finish tx
  where identity=Key tenant (text "request" request)
        handle=case field "tx" request of String s->s; _->""
        finish tx
          | not (valid (table e) tx) = (err "conflict",e)
          | not (unique proposed) = (err "unique",e)
          | length (D.journal (device e))+length fs>D.capacity (device e) = (err "capacity",e)
          | has "fault" request = (err "interrupted",recoverEngine e {device=nextDevice})
          | otherwise = (obj [("committed",int next)],e {device=nextDevice,table=proposed,revision=next,receipts=M.insert identity next (receipts e),transactions=M.delete handle (transactions e)})
          where next=revision e+1
                proposed=overlay (table e) next tx
                fs=frames (text "request" request) next tx
                nextDevice=D.append fs (fault request) (device e)
call :: Value -> Engine -> (Value,Engine)
call request e = case text "op" request of
  "init" -> (ok,reset (number "capacity" request))
  "stats" -> (obj [("revision",int (revision e)),("journal_frames",int (length (D.journal (device e)))),("capacity",int (D.capacity (device e))),("transactions",int (M.size (transactions e)))],e)
  "crash" -> let next=recoverEngine e in (obj [("recovered",int (revision next))],next)
  "checkpoint" -> let next=e {device=D.publish (image e) (fault request) (device e)} in
    if has "fault" request then (err "interrupted",recoverEngine next) else (obj [("checkpoint",int (revision e))],next)
  op | version==2 && text "actor" request/=tenant -> (err "forbidden",e)
     | otherwise -> ordinary op
  where version=if has "v" request then number "v" request else 1
        tenant=if version==1 then "legacy" else text "tenant" request
        ordinary "inspect"=(D.inspect tenant (device e),e)
        ordinary "load"
          | revision e/=0 || not (M.null (transactions e)) || not (null (D.journal (device e))) || D.loaded (device e) || not (null (items (field "entries" (D.image (device e))))) || not (null (items (field "receipts" (D.image (device e))))) = (err "not_empty",e)
          | otherwise = let next=recoverEngine e {device=D.loadImage (field "image" request) tenant (device e)} in (obj [("loaded",int (revision next))],next)
        ordinary "begin"
          | M.member (text "tx" request) (transactions e) = (err "transaction_exists",e)
          | otherwise = (obj [("snapshot",int (revision e))],e {transactions=M.insert (text "tx" request) (begin tenant (revision e) (table e)) (transactions e)})
        ordinary "commit"=commit request tenant e
        ordinary op=case M.lookup (text "tx" request) (transactions e) of
          Nothing -> (err "transaction_missing",e)
          Just tx | owner tx/=tenant -> (err "transaction_owner",e)
                  | otherwise -> operation op tx
        save tx result=(result,e {transactions=M.insert (text "tx" request) tx (transactions e)})
        operation "read" tx=let (r,next)=readRow (text "id" request) tx in save next (obj [("record",wire version r)])
        operation "scan" tx=let (rows,next)=scan (text "lo" request) (text "hi" request) tx in save next (obj [("records",arr (map (wire version . Just) rows))])
        operation "lookup" tx=let (rows,next)=lookupAlias (text "alias" request) tx in save next (obj [("records",arr (map (wire version . Just) rows))])
        operation "put" tx=save tx {writes=M.insert (text "id" request) (Just (record tenant (text "id" request) request)) (writes tx)} ok
        operation "delete" tx=save tx {writes=M.insert (text "id" request) Nothing (writes tx)} ok
        operation "abort" _=(ok,e {transactions=M.delete (text "tx" request) (transactions e)})
        operation _ _=error "unknown operation"
