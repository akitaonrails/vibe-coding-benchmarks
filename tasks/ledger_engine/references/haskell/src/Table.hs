{-# LANGUAGE OverloadedStrings #-}
module Table where
import Domain
import Data.Aeson hiding (Key)
import Data.Text (Text)
import qualified Data.Map.Strict as M
import qualified Data.Set as S
version :: Text -> Text -> Table -> Int
version tenant ident table = maybe 0 entryVersion (M.lookup (Key tenant ident) table)
row :: Text -> Text -> Table -> Maybe Row
row tenant ident table = maybe Nothing entryRow (M.lookup (Key tenant ident) table)
live :: Text -> Table -> [Row]
live tenant table = [r | (Key owner _,Entry _ (Just r))<-M.toAscList table, owner==tenant]
interval :: Text -> Text -> Text -> Table -> M.Map Text Int
interval tenant lo hi table = M.fromList [(ident,v) | (Key owner ident,Entry v _)<-M.toList table,owner==tenant,lo<=ident,ident<hi]
aliasVersions :: Text -> Text -> Table -> M.Map Text Int
aliasVersions tenant name table = M.fromList [(rowId r, version tenant (rowId r) table) | r<-live tenant table,alias r==Just name]
unique :: Table -> Bool
unique table = let keys=[Key tenant name | (Key tenant _,Entry _ (Just r))<-M.toList table,Just name<-[alias r]] in length keys==S.size (S.fromList keys)
imageEntries :: Table -> Value
imageEntries table = arr [obj [("tenant",String t),("id",String i),("version",int v),("row",optionalRowJSON r)] | (Key t i,Entry v r)<-M.toAscList table]
