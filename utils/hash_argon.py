from argon2 import PasswordHasher, exceptions

def summon(data:str, salt:str="www.zhongrongxinfu.cn"):
    return PasswordHasher().hash(data, salt=salt.encode())

def verify(data:str, hash:str):
    """
        1: Success; -1: Verify Error; -2: InvalidHash Error; -3: Unknow Error
    """
    try:
        PasswordHasher().verify(hash, data)
        return (1, "Success")
    except exceptions.VerifyMismatchError:
        return (-3, "Verify Error")
    except exceptions.InvalidHashError:
        return (-4, "InvalidHash Error")
    except Exception as error:
        return (-5, str(error))

if __name__ == "__main__":
    print(summon("sdsd"))