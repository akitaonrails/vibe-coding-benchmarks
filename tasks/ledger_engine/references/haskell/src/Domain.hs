{-# LANGUAGE OverloadedStrings #-}
module Domain where
import Data.Aeson hiding (Key)
import qualified Data.Aeson.Key as K
import qualified Data.Aeson.KeyMap as KM
import qualified Data.Map.Strict as M
import Data.Text (Text)
import qualified Data.Vector as V

data Key = Key Text Text deriving (Eq,Ord,Show)
data Entry = Entry { entryVersion :: Int, entryRow :: Maybe Row } deriving (Eq,Show)
type Table = M.Map Key Entry
type Receipts = M.Map Key Int
field :: Text -> Value -> Value
field k (Object o) = KM.lookup (K.fromText k) o `orElse` Null
field _ _ = Null
orElse :: Maybe a -> a -> a
orElse (Just x) _ = x
orElse Nothing x = x
text :: Text -> Value -> Text
text k v = case field k v of String s -> s; _ -> error "string field required"
number :: Text -> Value -> Int
number k v = case fromJSON (field k v) of Success n -> n; _ -> error "integer field required"
has :: Text -> Value -> Bool
has k (Object o) = KM.member (K.fromText k) o
has _ _ = False
items :: Value -> [Value]
items (Array a) = V.toList a
items _ = []
set :: Text -> Value -> Value -> Value
set k v (Object o) = Object (KM.insert (K.fromText k) v o)
set _ _ _ = error "object required"
remove :: Text -> Value -> Value
remove k (Object o) = Object (KM.delete (K.fromText k) o)
remove _ v = v
obj :: [(Text,Value)] -> Value
obj = Object . KM.fromList . map (\(k,v)->(K.fromText k,v))
int :: Int -> Value
int = toJSON
arr :: [Value] -> Value
arr = toJSON
ok :: Value
ok = obj [("ok",Bool True)]
err :: Text -> Value
err code = obj [("error",String code)]
data Presence a = Missing | Present a deriving (Eq,Show)
data Row = Row { rowTenant :: Text, rowId :: Text, rowValue :: Int,
                 rowAlias :: Presence (Maybe Text), rowNote :: Presence Value } deriving (Eq,Show)
data Frame = BeginFrame Text Text Int Int | EditFrame Text (Maybe Row) | SealFrame Int | TornFrame deriving (Eq,Show)
record :: Text -> Text -> Value -> Row
record tenant ident request = Row tenant ident (number "value" request) optionalAlias optionalNote
  where optionalAlias=if has "alias" request then Present (case field "alias" request of String name->Just name; _->Nothing) else Missing
        optionalNote=if has "note" request then Present (field "note" request) else Missing
rowJSON :: Row -> Value
rowJSON r = obj ([("tenant",String (rowTenant r)),("id",String (rowId r)),("value",int (rowValue r))]
  ++ (case rowAlias r of Missing->[]; Present name->[("alias",maybe Null String name)])
  ++ (case rowNote r of Missing->[]; Present note->[("note",note)]))
optionalRowJSON :: Maybe Row -> Value
optionalRowJSON = maybe Null rowJSON
wire :: Int -> Maybe Row -> Value
wire version r = if version==1 then remove "tenant" encoded else encoded
  where encoded=optionalRowJSON r
alias :: Row -> Maybe Text
alias r = case rowAlias r of Present name->name; Missing->Nothing
frameJSON :: Frame -> Value
frameJSON (BeginFrame tenant request revision count) = obj [("kind",String "BEGIN"),("tenant",String tenant),("request",String request),("revision",int revision),("count",int count)]
frameJSON (EditFrame ident r) = obj [("kind",String "EDIT"),("id",String ident),("row",optionalRowJSON r)]
frameJSON (SealFrame revision) = obj [("kind",String "SEAL"),("revision",int revision)]
frameJSON TornFrame = obj [("kind",String "TORN")]
