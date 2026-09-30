# A container keeps an instance, it does not call it

`items.append(State())` on a list, a set, or a dictionary stores the instance. The methods run
where the stored value is read back, and a call there is resolved by the type of the value or is
guarded by the method name. Storing an instance therefore does not make every method of its class
reachable. A method that the reading code calls stays live.
